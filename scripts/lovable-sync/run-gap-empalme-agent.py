#!/usr/bin/env python3
"""Agente Cursor focalizado en cerrar gaps del manifiesto gap-manifest.json."""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from reglas_paths import min_reglas_front_bytes, operativas_paths

API = "https://api.cursor.com/v1/agents"
POLL_INTERVAL = 20
POLL_TIMEOUT = 2400
AGENT_DIR = "ReglasAgente"
WEB_REPO_HOST = "github.com/doeventsrepo/DoEventsWEB"
MIN_RULES_BYTES = min_reglas_front_bytes()
TERMINAL_RUN = frozenset({"FINISHED", "ERROR", "CANCELLED", "CANCELED", "EXPIRED"})


def api(method: str, path: str, body: dict | None = None) -> dict:
    key = os.environ["CURSOR_API_KEY"]
    url = f"{API}{path}" if path else API
    data = json.dumps(body).encode() if body is not None else None
    basic = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def gh_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def read_optional(path: str) -> str:
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def web_branch_from_run(run: dict) -> str | None:
    git = run.get("git") or {}
    for item in git.get("branches") or []:
        repo = (item.get("repoUrl") or "").lower()
        if WEB_REPO_HOST in repo and item.get("branch"):
            return item["branch"]
    return None


def wait_run(agent_id: str, run_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    last_status = ""
    while time.time() < deadline:
        try:
            state = api("GET", f"/{agent_id}/runs/{run_id}")
        except urllib.error.HTTPError as e:
            print(f"Poll error {e.code}: {e.read().decode()}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
            continue
        status = (state.get("status") or "unknown").upper()
        if status != last_status:
            print(f"Run {run_id}: {status}")
            last_status = status
        if status in TERMINAL_RUN:
            return state
        time.sleep(POLL_INTERVAL)
    return {}


def main() -> int:
    if os.environ.get("DSF_BLOCK_GITHUB") == "1" or os.environ.get("DSF_LOCAL_MODE") == "1":
        print("ERROR: gap agent bloqueado en modo local. Usa simulation/scripts/local-apply-empalme.py", file=sys.stderr)
        return 1
    if not os.environ.get("CURSOR_API_KEY"):
        print("ERROR: CURSOR_API_KEY requerido", file=sys.stderr)
        return 1

    web_dir = os.environ.get("WEB_DIR", "")
    lovable_dir = os.environ.get("LOVABLE_DIR", ".")
    cicd_dir = os.environ.get("CICD_DIR", "")
    gap_manifest_path = os.environ.get("GAP_MANIFEST_PATH", "")

    if not web_dir or not gap_manifest_path or not os.path.exists(gap_manifest_path):
        print("ERROR: WEB_DIR y GAP_MANIFEST_PATH requeridos", file=sys.stderr)
        return 1

    gap_manifest = json.loads(read_optional(gap_manifest_path) or "{}")
    if not gap_manifest.get("gaps"):
        print("Sin gaps en el batch — omitir agente")
        gh_output("agent_skipped", "true")
        return 0

    rules_content = read_optional(os.path.join(web_dir, AGENT_DIR, "reglas-front.md"))
    if len(rules_content.strip()) < MIN_RULES_BYTES:
        print(f"BLOQUEADO: leer {AGENT_DIR}/reglas-front.md antes de empalmar gaps", file=sys.stderr)
        return 1

    ops = operativas_paths(Path(cicd_dir)) if cicd_dir else {}
    prompt_gap = read_optional(str(ops.get("promptGapEmpalme", ""))) if ops else ""
    if not prompt_gap and cicd_dir:
        prompt_gap = read_optional(str(Path(cicd_dir) / "Reglas/operativas/prompt-gap-empalme.md"))

    reglas_doc = read_optional(str(ops["reglamento"])) if ops else ""
    regla_comparacion = read_optional(str(ops["reglaComparacion"])) if ops else ""
    instructions = read_optional(str(ops["promptEmpalme"])) if ops else ""

    branch = os.environ.get("AGENT_BRANCH", "feature/cicd/dev-automation")
    run_id = gap_manifest.get("workflowRunId", os.environ.get("GITHUB_RUN_ID", "local"))
    gap_json = json.dumps(gap_manifest, indent=2, ensure_ascii=False)

    mandatory = f"""
# CIERRE DE GAPS — EMPALME FOCALIZADO (batch {gap_manifest.get('batchIndex', 1)})

Implementa **TODOS** los gaps listados en gap-manifest.json para este batch.
Objetivo: cada ítem queda `DONE` en frontend o `BACKEND_REQUIRED` documentado.

## Fidelidad visual DSF (obligatorio cuando DSF_DESIGN_FIDELITY=1)
- **Preservar** el diseño Lovable: labels, toggles, colores, gradientes, variables CSS (`--*`), `data-*` theme attrs.
- **Prohibido reinterpretar** UX (ej. cambiar tema dorado por claro/oscuro, cambiar copy o iconografía).
- Solo adaptar: imports `@/` → `@lovable/`, quitar mocks/supabase, conservar bridge/API existente en WEB.
- Para archivos nuevos en Lovable: crear equivalente WEB con misma UI visible que Lovable tras transform de imports.

## Métricas actuales
- Similitud global: {gap_manifest.get('beforeSimilarityPercent', 0)}% (objetivo {gap_manifest.get('targetSimilarityPercent', 98)}%)
- Gaps totales pendientes: {gap_manifest.get('totalPendingGaps', 0)}
- Gaps en este batch: {gap_manifest.get('gapsInBatch', 0)}

## OBLIGATORIO AL TERMINAR
1. Actualizar `ReglasAgente/decision-log.md` — entrada `gap-empalme-{run_id}`
2. Actualizar `ReglasAgente/cambios-lovable.json` — run con gapsClosed y gapsBackendRequired
3. Actualizar `ReglasAgente/impacto-backend.md` — tablas Empalme realizado + Backend pendiente para 100%
4. Crear/actualizar `docs/changes/gap-empalme-latest.md` — resumen ejecutivo
5. `npm run build:devaws` exitoso
6. Push a rama `{branch}` únicamente

## PROHIBIDO
- Copy-paste literal de mocks/supabase desde Lovable
- Mocks en runtime
- Ramas feature/lovable/adapt-*
- Reinterpretar diseño visual respecto a Lovable (ver fidelidad DSF arriba)

## Reglas completas
{rules_content}
"""

    text = f"""{instructions}

{prompt_gap}

{reglas_doc}

{regla_comparacion}

{mandatory}

## Manifiesto de gaps (implementar este batch)
```json
{gap_json}
```

## Contexto Lovable
{read_optional(os.path.join(lovable_dir, ".ai", "agent-sync-context.md")) or "_Sin contexto adicional_"}
"""

    repos = [{"url": "https://github.com/doeventsrepo/DoEventsWEB", "startingRef": branch}]
    if os.environ.get("AGENT_INCLUDE_BACK", "false").lower() == "true":
        back_ref = os.environ.get("BACK_STARTING_REF", branch)
        repos.append({"url": "https://github.com/doeventsrepo/DoEventsBack", "startingRef": back_ref})

    payload = {
        "prompt": {"text": text},
        "model": {"id": os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5")},
        "repos": repos,
        "workOnCurrentBranch": True,
        "autoCreatePR": False,
        "skipReviewerRequest": True,
        "name": f"Gap empalme DEV batch-{gap_manifest.get('batchIndex', 1)} [{run_id}]",
    }

    try:
        created = api("POST", "", payload)
    except urllib.error.HTTPError as e:
        print(f"Cursor API {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1

    agent = created.get("agent") or {}
    run = created.get("run") or {}
    agent_id = agent.get("id") or created.get("id")
    run_id_cursor = run.get("id") or agent.get("latestRunId")
    agent_url = agent.get("url", "")

    print(f"Agente gaps: {agent_id} run: {run_id_cursor} -> {branch}")
    if agent_url:
        print(f"URL: {agent_url}")

    gh_output("cursor_agent_id", agent_id or "")
    gh_output("cursor_run_id", run_id_cursor or "")
    gh_output("agent_skipped", "false")

    if os.environ.get("AGENT_WAIT", "true").lower() == "false":
        gh_output("agent_pushed_branch", branch)
        return 0

    if not agent_id or not run_id_cursor:
        print("ERROR: respuesta API sin agent/run id", file=sys.stderr)
        return 1

    final = wait_run(agent_id, run_id_cursor)
    status = (final.get("status") or "unknown").upper()
    pushed = web_branch_from_run(final) or branch
    gh_output("agent_pushed_branch", pushed)

    result = final.get("result") or final.get("text") or ""
    if result:
        print(result[:12000])

    if status != "FINISHED":
        print(f"ERROR: run termino con status {status}", file=sys.stderr)
        return 1

    print(f"OK: gap empalme en rama {pushed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
