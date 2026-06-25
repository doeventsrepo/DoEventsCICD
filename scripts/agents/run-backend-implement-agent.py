#!/usr/bin/env python3
"""
BSF — Agente implementador backend vía Cursor API.

Aplica cambios detectados en frontend hacia DoEventsBack (rama feature/cicd/dev-automation).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).resolve().parent
LOVABLE_SYNC = AGENTS_DIR.parent / "lovable-sync"
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(LOVABLE_SYNC))

from agent_base import artifacts_dir, cicd_root, gh_output, invoke_cursor_agent, is_dry_run, load_config, read_optional, write_report

try:
    from backend_sync_log import append_log
except ImportError:
    def append_log(*_a, **_k):  # type: ignore
        return Path()


def build_prompt(
    delta: dict[str, Any],
    contracts: dict[str, Any],
    web_dir: Path,
    back_dir: Path,
    registry: dict[str, Any],
) -> str:
    prompt_path = cicd_root() / "Reglas" / "operativas" / "prompt-backend-sync.md"
    base = read_optional(prompt_path)
    impacto = read_optional(web_dir / "ReglasAgente" / "impacto-backend.md")

    items = [i for i in (delta.get("items") or []) if i.get("requiresBackend")]
    pending = [f for f in (contracts.get("findings") or []) if not f.get("implementedInDoEventsBack")]

    tasks: list[str] = []
    for item in items:
        domains = ", ".join(item.get("domains") or ["general"])
        fields = ", ".join(item.get("newFields") or [])
        types = ", ".join(item.get("changeTypes") or [])
        targets = item.get("lambdaTargets") or []
        lambda_hint = targets[0].get("lambdaDir") if targets else "ver backend-registry.json"
        tasks.append(
            f"- Archivo FE: `{item.get('path')}` | dominio: {domains} | "
            f"tipos: {types} | campos nuevos: {fields or 'N/A'} | lambda: `{lambda_hint}`"
        )

    contract_lines = [
        f"- Endpoint `{f.get('endpoint')}` en `{f.get('lovablePath')}` — implementar en Back"
        for f in pending[:25]
    ]

    return f"""{base}

---

## Contexto de ejecución BSF

- **WEB:** `{web_dir}`
- **BACK:** `{back_dir}`
- **Rama obligatoria:** `{registry.get('branch', 'feature/cicd/dev-automation')}`
- **API DEV:** `{registry.get('apiBaseDev', 'https://api-dev.doeventsapp.com')}`

## Cambios frontend que requieren backend

{chr(10).join(tasks) if tasks else "Sin items delta — revisar impacto-backend.md"}

## Contratos pendientes

{chr(10).join(contract_lines) if contract_lines else "Sin contratos bloqueados"}

## impacto-backend.md (DoEventsWEB)

```
{impacto[:12000]}
```

## Instrucciones de salida

1. Modifica handlers, validaciones, DynamoDB y serverless.dev.yml según dominio.
2. NO elimines endpoints existentes.
3. Usa sufijo `-dev` en tablas DynamoDB.
4. Documenta cada cambio en comentarios breves.
5. Si no puedes implementar algo, deja `// BSF_PENDING: motivo` en el handler.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF backend implement agent")
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--back-dir", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--delta-json", default="")
    args = parser.parse_args()

    run_id = args.run_id
    cfg = load_config()
    registry_path = cicd_root() / "dsf" / "backend-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}

    art = artifacts_dir(run_id)
    delta_path = Path(args.delta_json) if args.delta_json else art / f"backend-delta-{run_id}.json"
    contract_path = art / f"backend-contract-check-{run_id}.json"

    delta = json.loads(delta_path.read_text(encoding="utf-8")) if delta_path.is_file() else {}
    contracts = json.loads(contract_path.read_text(encoding="utf-8")) if contract_path.is_file() else {}

    if not delta.get("requiresBackendCount"):
        report = {"ok": True, "skipped": True, "reason": "sin cambios que requieran backend"}
        write_report(f"backend-implement-{run_id}.json", report, run_id)
        print(json.dumps(report, indent=2))
        return 0

    prompt = build_prompt(delta, contracts, Path(args.web_dir), Path(args.back_dir), registry)
    backend_repo = cfg.get("repositories", {}).get("backend", "doeventsrepo/DoEventsBack")
    branch = cfg.get("branches", {}).get("cicdBack", registry.get("branch", "feature/cicd/dev-automation"))

    append_log(
        "implement_start",
        level="info",
        message=f"Iniciando implementación backend — {delta.get('requiresBackendCount')} items",
        metadata={"domains": delta.get("domainsAffected")},
        run_id=run_id,
    )

    cursor_result = invoke_cursor_agent(
        name=f"BSF-backend-implement-{run_id}",
        prompt_text=prompt,
        repos=[{"url": f"https://github.com/{backend_repo}", "startingRef": branch}],
        wait=os.environ.get("BSF_WAIT_CURSOR", "1") == "1",
        model=cfg.get("agent", {}).get("defaultModel", "composer-2.5"),
    )

    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in delta.get("items") or []:
        if not item.get("requiresBackend"):
            continue
        entry = {
            "path": item.get("path"),
            "domains": item.get("domains"),
            "fields": item.get("newFields"),
            "lambdaDirs": [t.get("lambdaDir") for t in item.get("lambdaTargets") or []],
            "status": "delegated_to_cursor" if not is_dry_run() else "dry_run",
        }
        applied.append(entry)

    report = {
        "ok": bool(cursor_result.get("dryRun")) or (
            not cursor_result.get("httpError") and bool(cursor_result.get("agentId"))
        ),
        "dryRun": is_dry_run() or cursor_result.get("dryRun"),
        "cursor": cursor_result,
        "applied": applied,
        "failed": failed,
        "backendRepo": backend_repo,
        "branch": branch,
        "promptChars": len(prompt),
    }
    write_report(f"backend-implement-{run_id}.json", report, run_id)
    gh_output("backend_implement_ok", str(report["ok"]).lower())

    append_log(
        "implement_complete",
        level="info",
        message="Implementación delegada a Cursor API",
        fix_applied=not is_dry_run(),
        fix_summary=f"agentId={cursor_result.get('agentId', 'dry-run')}",
        run_id=run_id,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
