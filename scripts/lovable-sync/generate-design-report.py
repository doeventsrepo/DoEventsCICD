#!/usr/bin/env python3
"""Genera reporte MD de comparacion de diseño Lovable vs WEB."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: generate-design-report.py <design-comparison.json> <out.md> [run_id]", file=sys.stderr)
        return 1

    comparison = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    run_id = sys.argv[3] if len(sys.argv) > 3 else "local"

    overall = comparison.get("overallSimilarityPercent", 0)
    target = comparison.get("targetSimilarityPercent", 98)
    gap = comparison.get("alignmentGapPercent", 0)
    summary = comparison.get("summary", {})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "# Reporte — Comparación diseño Lovable vs DoEventsWEB",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| **Generado** | {ts} |",
        f"| **Run CICD** | {run_id} |",
        f"| **Similitud global** | **{overall}%** |",
        f"| **Objetivo** | {target}% |",
        f"| **Brecha** | {gap}% |",
        f"| **Archivos rastreados** | {comparison.get('trackedFiles', 0)} |",
        f"| **Requiere agente** | {comparison.get('requiresAgentForDesignAlignment', False)} |",
        "",
        "## Resumen",
        "",
        f"- Alineados (≥98%): {summary.get('aligned', 0)}",
        f"- Deriva menor (85–97%): {summary.get('minorDrift', 0)}",
        f"- Requieren empalme (<85%): {summary.get('needsAdaptation', 0)}",
        f"- Ausentes en WEB: {summary.get('missingInWeb', 0)}",
        "",
        "## Propósito",
        "",
        "Detectar diferencias de diseño entre Lovable y DoEventsWEB para que el agente "
        "**empalme** (adapte) el diseño actual sin copy-paste ni mocks en runtime.",
        "",
        "## Archivos con baja similitud (prioridad agente)",
        "",
    ]

    low = comparison.get("lowSimilarity") or []
    if low:
        lines.append("| Lovable | WEB | Similitud |")
        lines.append("|---------|-----|-----------|")
        for item in low[:30]:
            lines.append(
                f"| `{item['lovablePath']}` | `{item['webPath']}` | {item['similarityPercent']}% |"
            )
    else:
        lines.append("_Ninguno por debajo del 85%._")

    lines.extend(["", "## Ausentes en DoEventsWEB", ""])
    missing = comparison.get("missingInWeb") or []
    if missing:
        for m in missing[:30]:
            lines.append(f"- `{m}`")
    else:
        lines.append("_Todos los archivos Lovable rastreados tienen contraparte en WEB._")

    lines.extend(
        [
            "",
            "## Reglas de empalme",
            "",
            "- NO copiar/pegar archivos completos de Lovable",
            "- NO activar mocks de Lovable en `pages/` runtime",
            "- Adaptar en `lovable-bridge/` y componentes existentes",
            "- Tras adaptación: re-ejecutar comparación y buscar ≥98% similitud estructural",
            "",
            f"_JSON fuente: design-comparison.json — run {run_id}_",
        ]
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
