#!/usr/bin/env python3
"""Genera/actualiza artefactos en DoEventsWEB/ReglasAgente/."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = "ReglasAgente"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_json(path: Path) -> dict:
    default = {
        "version": "1.0",
        "description": "",
        "policy": {"noLiteralCopy": True, "noLovableMocksInRuntime": True},
        "runs": [],
    }
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"AVISO: {path} JSON inválido ({exc}) — reiniciando store", file=sys.stderr)
        return default


def classify_from_manifest(manifest: dict) -> list[str]:
    types: list[str] = []
    if manifest.get("hasUiChanges"):
        types.append("VISUAL")
    if manifest.get("hasRulesChanges"):
        types.append("FRONT_LOGIC")
    if not types:
        types.append("VISUAL")
    return types


def append_decision_log(web: Path, entry: dict) -> None:
    log_path = web / AGENT_DIR / "decision-log.md"
    if not log_path.exists():
        return

    types = entry.get("changeTypes", [])
    type_lines = "\n".join(
        f"- [{'x' if t in types else ' '}] {t}"
        for t in ("VISUAL", "FRONT_LOGIC", "BACKEND_REQUIRED", "RISKY")
    )
    files = entry.get("changedFiles", [])
    file_lines = "\n".join(f"- `{f}`" for f in files[:30]) or "- (ver cambios-lovable.json)"

    block = f"""
## [{entry.get('timestamp', utc_now())}] prepare-{entry.get('lovableSha', 'unknown')[:8]}

### 1. Resumen del cambio detectado
{entry.get('summary', 'Preparacion adaptacion Lovable -> DoEventsWEB')}

### 2. Tipo de cambio (preliminar)
{type_lines}

### 3. Archivos modificados en DoEventsWEB
- Pendiente — el agente adapta sin copia literal

### 4. Archivos modificados en DoEventsBack (si aplica)
- Pendiente evaluacion agente

### 5. Evidencia de que no se usaron mocks
- Sin port deterministico de componentes en esta fase.
- El agente debe usar `lovable-bridge/*` + `@doevents/shared`.

### 6. Resultado build/test
- `npm run build:devaws`: {entry.get('buildResult', 'pending')}

### 7. Riesgos pendientes
- Agente debe completar adaptacion y actualizar esta entrada.

---
"""
    content = log_path.read_text(encoding="utf-8")
    marker = "## Historial"
    if marker in content:
        content = content.replace(
            "_Inicializado. El agente completa cada entrada tras adaptar._",
            "",
        )
        content = content.replace(marker + "\n", marker + "\n" + block)
    else:
        content += block
    log_path.write_text(content, encoding="utf-8")


def main() -> int:
    if len(sys.argv) < 4:
        print("Uso: generate-agent-artifacts.py <lovable_dir> <web_dir> <manifest.json>")
        return 1

    web = Path(sys.argv[2])
    manifest = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    agent_dir = web / AGENT_DIR
    agent_dir.mkdir(parents=True, exist_ok=True)

    lovable_sha = manifest.get("lovableSha", "unknown")
    changed = [x.get("path", x) if isinstance(x, dict) else x for x in manifest.get("changedFiles", [])]

    dc = manifest.get("designComparison") or {}
    run_entry = {
        "id": f"prepare-{lovable_sha[:8]}",
        "lovableSha": lovable_sha,
        "before": manifest.get("before"),
        "timestamp": utc_now(),
        "workflowRunId": os.environ.get("GITHUB_RUN_ID"),
        "changeTypes": classify_from_manifest(manifest),
        "designSimilarityPercent": dc.get("overallSimilarityPercent"),
        "designSimilarityTarget": dc.get("targetSimilarityPercent", 98),
        "designGapPercent": dc.get("alignmentGapPercent"),
        "requiresDesignAlignment": dc.get("requiresAgentForDesignAlignment"),
        "summary": (
            f"Manifiesto: UI={manifest.get('hasUiChanges')}, "
            f"reglas={manifest.get('hasRulesChanges')}, {len(changed)} archivo(s); "
            f"similitud diseño={dc.get('overallSimilarityPercent', 'n/a')}%"
        ),
        "changedFilesLovable": changed,
        "webFilesModified": [],
        "backFilesModified": [],
        "mocksUsed": False,
        "buildResult": os.environ.get("BUILD_RESULT", "pending"),
        "pendingRisks": ["Adaptacion pendiente por agente Cursor"],
        "agentStatus": "pending",
    }

    cambios_path = agent_dir / "cambios-lovable.json"
    store = load_json(cambios_path)
    store["runs"] = [r for r in store.get("runs", []) if r.get("lovableSha") != lovable_sha]
    store.setdefault("runs", []).append(run_entry)
    cambios_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    append_decision_log(web, run_entry)
    print(f"Artefactos en {agent_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
