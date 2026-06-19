#!/usr/bin/env python3
"""Invoca Cursor Cloud Agents API — adaptacion obligatoria con ReglasAgente/."""
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
POLL_INTERVAL = 15
POLL_TIMEOUT = 900
AGENT_DIR = "ReglasAgente"
MIN_RULES_BYTES = min_reglas_front_bytes()


def api(method: str, path: str, body: dict | None = None) -> dict:
    key = os.environ["CURSOR_API_KEY"]
    url = f"{API}{path}"
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


def read_optional(path: str) -> str:
    return open(path, encoding="utf-8").read() if os.path.exists(path) else ""


def wait_agent(agent_id: str) -> dict:
    deadline = time.time() + POLL_TIMEOUT
    last_status = ""
    while time.time() < deadline:
        try:
            state = api("GET", f"/{agent_id}")
        except urllib.error.HTTPError as e:
            print(f"Poll error {e.code}: {e.read().decode()}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
            continue
        status = state.get("status") or state.get("agent", {}).get("status") or "unknown"
        if status != last_status:
            print(f"Agente {agent_id}: {status}")
            last_status = status
        if status in ("completed", "finished", "succeeded", "success"):
            return state
        if status in ("failed", "error", "cancelled", "canceled"):
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

    web_ref = os.environ.get("WEB_STARTING_REF", "feature/cicd/dev-automation")
    back_ref = os.environ.get("BACK_STARTING_REF", "feature/cicd/dev-automation")
    repos = [
        {"url": "https://github.com/doeventsrepo/DoEventsWEB", "startingRef": web_ref},
    ]
    if os.environ.get("AGENT_INCLUDE_BACK", "true").lower() == "true":
        repos.append({"url": "https://github.com/doeventsrepo/DoEventsBack", "startingRef": back_ref})

    payload = {
        "prompt": {"text": text},
        "model": {"id": os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5")},
        "repos": repos,
        "target": {
            "autoCreatePr": os.environ.get("AGENT_AUTO_PR", "false").lower() == "true",
            "branchName": branch,
        },
    }

    try:
        created = api("POST", "", payload)
    except urllib.error.HTTPError as e:
        print(f"Cursor API {e.code}: {e.read().decode()}", file=sys.stderr)
        return 1

    agent_id = created.get("id") or created.get("agent", {}).get("id")
    print(f"Agente: {agent_id} -> {branch}")

    if os.environ.get("AGENT_WAIT", "true").lower() != "false" and agent_id:
        final = wait_agent(agent_id)
        result = final.get("result") or final.get("summary") or ""
        if result:
            print(result[:5000])

    return 0


if __name__ == "__main__":
    sys.exit(main())
