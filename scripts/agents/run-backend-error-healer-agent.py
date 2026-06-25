#!/usr/bin/env python3
"""
BSF — Agente healer: lee errores JSONL y corrige vía Cursor API de forma autónoma.
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
    from backend_sync_log import append_log, read_logs
except ImportError:
    def append_log(*_a, **_k):  # type: ignore
        return Path()

    def read_logs(*_a, **_k):  # type: ignore
        return []


def build_healer_prompt(errors: list[dict[str, Any]], back_dir: Path, registry: dict[str, Any]) -> str:
    reglamento = read_optional(cicd_root() / "Reglas" / "operativas" / "reglamento-cursor-api.md")
    error_block = json.dumps(errors[-20:], indent=2, ensure_ascii=False)

    return f"""# BSF Error Healer — corrección autónoma backend

Eres un agente SRE/DevOps especializado en serverless AWS (Lambda, API Gateway, DynamoDB, S3).

## Entorno

- **BACK:** `{back_dir}`
- **Rama:** `{registry.get('branch', 'feature/cicd/dev-automation')}`
- **Stage:** dev | **Region:** sa-east-1
- **Registry:** `DoEventsCICD/dsf/backend-registry.json`

## Reglamento

{reglamento[:8000]}

## Errores detectados (JSONL BSF)

```json
{error_block}
```

## Tareas

1. Analiza cada error (deploy, runtime, validación, schema DynamoDB).
2. Corrige el código en DoEventsBack (handlers, serverless.dev.yml, IAM, env vars).
3. NO borres recursos AWS ni tablas.
4. Tras cada fix, documenta en comentario `// BSF_HEALER: <resumen>`.
5. Si el error es de infraestructura no codeable, deja nota en handler.

## Salida esperada

- Código corregido en lambdas afectadas
- Sin secretos hardcodeados
- Compatible con api-dev.doeventsapp.com
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF backend error healer")
    parser.add_argument("--back-dir", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--max-heals", type=int, default=3)
    args = parser.parse_args()

    run_id = args.run_id
    cfg = load_config()
    registry_path = cicd_root() / "dsf" / "backend-registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.is_file() else {}

    errors = [e for e in read_logs(run_id) if e.get("level") in ("error", "warn") or e.get("error")]
    deploy_errors = [e for e in read_logs(run_id) if e.get("event") in ("deploy_failed", "lambda_error", "heal_required")]

    candidates = deploy_errors or errors
    if not candidates:
        report = {"ok": True, "healed": 0, "skipped": True, "reason": "sin errores en log"}
        write_report(f"backend-healer-{run_id}.json", report, run_id)
        print(json.dumps(report, indent=2))
        return 0

    to_heal = candidates[-args.max_heals:]
    backend_repo = cfg.get("repositories", {}).get("backend", "doeventsrepo/DoEventsBack")
    branch = cfg.get("branches", {}).get("cicdBack", "feature/cicd/dev-automation")

    append_log(
        "healer_start",
        level="info",
        message=f"Healer procesando {len(to_heal)} errores",
        run_id=run_id,
    )

    prompt = build_healer_prompt(to_heal, Path(args.back_dir), registry)
    cursor_result = invoke_cursor_agent(
        name=f"BSF-backend-healer-{run_id}",
        prompt_text=prompt,
        repos=[{"url": f"https://github.com/{backend_repo}", "startingRef": branch}],
        wait=os.environ.get("BSF_WAIT_CURSOR", "1") == "1",
    )

    for err in to_heal:
        append_log(
            "heal_attempted",
            level="info",
            message=err.get("message", "error procesado"),
            domain=err.get("domain"),
            lambda_dir=err.get("lambdaDir"),
            error=err.get("error"),
            fix_applied=not is_dry_run(),
            fix_summary=f"cursor agent {cursor_result.get('agentId', 'dry-run')}",
            run_id=run_id,
        )

    report = {
        "ok": True,
        "errorsProcessed": len(to_heal),
        "cursor": cursor_result,
        "dryRun": is_dry_run() or cursor_result.get("dryRun"),
    }
    write_report(f"backend-healer-{run_id}.json", report, run_id)
    gh_output("backend_healer_count", str(len(to_heal)))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
