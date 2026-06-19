#!/usr/bin/env python3
"""Invoca Cursor Cloud Agents API v1 — adaptacion obligatoria con ReglasAgente/."""
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
POLL_TIMEOUT = 1800
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
    if not os.environ.get("CURSOR_API_KEY"):
        print("ERROR: CURSOR_API_KEY requerido para adaptacion", file=sys.stderr)
        return 1

    lovable_dir = os.environ.get("LOVABLE_DIR", ".")
    web_dir = os.environ.get("WEB_DIR", "")
    if not web_dir:
        print("ERROR: WEB_DIR requerido", file=sys.stderr)
        return 1

    rules_path = os.path.join(web_dir, AGENT_DIR, "reglas-front.md")
    rules_content = read_optional(rules_path)
    if len(rules_content.strip()) < MIN_RULES_BYTES:
        print(f"BLOQUEADO: leer y cumplir {AGENT_DIR}/reglas-front.md antes de adaptar", file=sys.stderr)
        return 1

    manifest_raw = read_optional(os.path.join(lovable_dir, "lovable-change-manifest.json")) or "{}"
    manifest = json.loads(manifest_raw)
    lovable_sha = manifest.get("lovableSha", os.environ.get("LOVABLE_SHA", "unknown"))

    cicd_dir = os.environ.get("CICD_DIR", "")
    if cicd_dir:
        ops = operativas_paths(Path(cicd_dir))
        instructions = read_optional(str(ops["promptEmpalme"]))
        reglas_doc = read_optional(str(ops["reglamento"]))
        regla_comparacion = read_optional(str(ops["reglaComparacion"]))
    else:
        instructions = read_optional(os.path.join(lovable_dir, ".ai", "prompts", "port-lovable-to-web.md"))
        reglas_doc = ""
        regla_comparacion = ""

    design_cmp_path = os.path.join(cicd_dir, "design-comparison.json") if cicd_dir else ""
    design_cmp_raw = read_optional(design_cmp_path) if design_cmp_path else ""
    if not design_cmp_raw and manifest.get("designComparison"):
        design_cmp_raw = json.dumps(manifest["designComparison"], indent=2)

    context = read_optional(os.path.join(lovable_dir, ".ai", "agent-sync-context.md"))
    if not context and cicd_dir:
        context = read_optional(os.path.join(cicd_dir, ".ai", "agent-sync-context.md"))

    branch = os.environ.get("AGENT_BRANCH", f"feature/lovable/adapt-{lovable_sha[:8]}")
    web_ref = os.environ.get("WEB_STARTING_REF", "feature/cicd/dev-automation")
    back_ref = os.environ.get("BACK_STARTING_REF", "feature/cicd/dev-automation")

    mandatory = f"""
# CONDICION DE EJECUCION — EMPALME OBLIGATORIO (NO COPY-PASTE)

Has leido `ReglasAgente/reglas-front.md`. Cumple TODAS las secciones (1-15).

## ENTORNO OBJETIVO
- Despliegue automatico: **DEV sa-east-1** (`dev.doeventsapp.com`, `api-dev.doeventsapp.com`)
- **PROHIBIDO** desplegar o configurar QA en este run
- Build obligatorio: `npm run build:devaws` (NO build:qa)

## EMPALME (adaptacion) — OBLIGATORIO
- Interpreta la intencion UX/reglas de Lovable e integrala en componentes **EXISTENTES**
- **Comparacion diseño**: implementa TODAS las diferencias en design-comparison.json (objetivo ≥98% similitud)
- Reutiliza `lovable-bridge/*`, `@doevents/shared`, servicios API reales
- Valida campos, props, endpoints y tablas DynamoDB `-dev` antes de cambiar codigo
- Si Lovable trae mockData/sampleData: **NO** llevarlo a runtime; usar hooks/servicios reales
- Si falta endpoint backend: documentar en `impacto-backend.md` como BACKEND_REQUIRED sin inventar datos

## PROHIBIDO
- Copiar/pegar archivos completos de Lovable sobre `packages/shell/src/lovable/`
- Sobrescribir MapView, ProfileView, LovableLayout sin adaptacion justificada
- Usar mocks de Lovable en `pages/` o desconectar backend
- Push a ramas main, develop, release o release/*
- Commit sin actualizar ReglasAgente/cambios-lovable.json, decision-log.md

## OBLIGATORIO AL TERMINAR
1. Resumen del empalme (que cambio y por que)
2. Tipo: VISUAL / FRONT_LOGIC / BACKEND_REQUIRED / RISKY
3. Archivos WEB modificados (lista)
4. Archivos DoEventsBack (si aplica, rama feature/cicd/dev-automation)
5. Evidencia mocksUsed: false
6. `npm run build:devaws` exitoso
7. Re-comparar diseño y registrar % similitud antes/después en decision-log.md
8. Riesgos pendientes en decision-log.md
9. Push a rama `{branch}` (feature/lovable/*)

## Reglas completas
{rules_content}
"""

    text = f"""{instructions}

{reglas_doc}

{regla_comparacion}

{mandatory}

## Manifiesto
```json
{manifest_raw}
```

## Comparacion diseño Lovable vs WEB (prioridad empalme)
```json
{design_cmp_raw or "_Sin comparacion — ejecutar compare-design-similarity.py_"}
```

## Contexto
{context or "_Sin contexto_"}
"""

    repos = [{"url": "https://github.com/doeventsrepo/DoEventsWEB", "startingRef": branch}]
    if os.environ.get("AGENT_INCLUDE_BACK", "false").lower() == "true":
        repos.append({"url": "https://github.com/doeventsrepo/DoEventsBack", "startingRef": back_ref})

    payload = {
        "prompt": {"text": text},
        "model": {"id": os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5")},
        "repos": repos,
        "workOnCurrentBranch": True,
        "autoCreatePR": os.environ.get("AGENT_AUTO_PR", "false").lower() == "true",
        "skipReviewerRequest": True,
        "name": f"Lovable empalme DEV {lovable_sha[:8]}",
    }

    try:
        created = api("POST", "", payload)
    except urllib.error.HTTPError as e:
        print(f"Cursor API {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1

    agent = created.get("agent") or {}
    run = created.get("run") or {}
    agent_id = agent.get("id") or created.get("id")
    run_id = run.get("id") or agent.get("latestRunId")
    agent_url = agent.get("url", "")
    print(f"Agente: {agent_id} run: {run_id} -> rama objetivo {branch}")
    if agent_url:
        print(f"URL: {agent_url}")
    gh_output("cursor_agent_id", agent_id or "")
    gh_output("cursor_run_id", run_id or "")

    if os.environ.get("AGENT_WAIT", "true").lower() == "false":
        gh_output("agent_pushed_branch", branch)
        return 0

    if not agent_id or not run_id:
        print("ERROR: respuesta API sin agent/run id", file=sys.stderr)
        return 1

    final = wait_run(agent_id, run_id)
    status = (final.get("status") or "unknown").upper()
    pushed = web_branch_from_run(final) or branch
    gh_output("agent_pushed_branch", pushed)

    result = final.get("result") or final.get("text") or ""
    if result:
        print(result[:8000])

    if status != "FINISHED":
        print(f"ERROR: run termino con status {status}", file=sys.stderr)
        return 1

    print(f"OK: empalme en rama {pushed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
