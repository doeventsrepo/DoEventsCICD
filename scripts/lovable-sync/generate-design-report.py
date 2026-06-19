#!/usr/bin/env python3
"""Genera reporte MD de comparacion de diseño Lovable vs WEB con checklist QA."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from design_validation_hints import AREA_ORDER, DEV_URL, build_validation_checklist, group_by_area


def _phase_label(run_id: str) -> str:
    if run_id.endswith("-pre"):
        return "Antes del agente (gaps pendientes)"
    if run_id.endswith("-post"):
        return "Después del empalme (validar ajustes)"
    return "Comparación actual"


def _render_checklist_item(item: dict, *, before_sim: float | None = None) -> list[str]:
    lines: list[str] = []
    status = item.get("statusLabel", item.get("status", ""))
    sim = item.get("similarityPercent", 0)
    delta = ""
    if before_sim is not None:
        diff = round(sim - before_sim, 2)
        if diff > 0:
            delta = f" _(mejoró +{diff}% vs pre-agente)_"
        elif diff < 0:
            delta = f" _(regresión {diff}%)_"

    lines.append(
        f"- [ ] **{item['feature']}** — _{status}_ · similitud **{sim}%**{delta}"
    )
    lines.append(f"  - **Dónde:** {item['where']} ({DEV_URL})")
    lines.append(f"  - **Acción:** {item['action']}")
    for check in item.get("checks") or []:
        lines.append(f"  - Validar: {check}")
    lines.append(f"  - _Componente Lovable: `{item.get('lovablePath', '')}`_")
    return lines


def _similarity_map(comparison: dict) -> dict[str, float]:
    return {e["lovablePath"]: float(e.get("similarityPercent", 0)) for e in comparison.get("files") or []}


def render_validation_section(
    comparison: dict,
    *,
    before: dict | None = None,
    max_per_area: int = 15,
) -> list[str]:
    checklist = comparison.get("validationChecklist") or build_validation_checklist(comparison)
    before_map = _similarity_map(before) if before else {}

    lines = [
        "## Qué validar manualmente en DEV",
        "",
        f"**Entorno:** [{DEV_URL}]({DEV_URL})",
        "",
        "Lista accionable derivada de gaps Lovable vs DoEventsWEB. "
        "Marque cada ítem tras revisar en DEV que el diseño coincida con Lovable "
        "(datos reales, sin mocks).",
        "",
    ]

    if before:
        before_overall = before.get("overallSimilarityPercent", 0)
        after_overall = comparison.get("overallSimilarityPercent", 0)
        lines.extend(
            [
                "| Métrica | Valor |",
                "|---------|-------|",
                f"| Similitud pre-agente | **{before_overall}%** |",
                f"| Similitud post-agente | **{after_overall}%** |",
                f"| Mejora | **{round(after_overall - before_overall, 2)}%** |",
                "",
            ]
        )

    grouped = group_by_area(checklist)
    if not grouped:
        lines.append("_No hay gaps pendientes — diseño alineado al objetivo (≥98%)._")
        lines.append("")
        return lines

    for area in AREA_ORDER:
        items = grouped.get(area)
        if not items:
            continue
        lines.append(f"### {area}")
        lines.append("")
        for item in items[:max_per_area]:
            bsim = before_map.get(item.get("lovablePath", "")) if before_map else None
            lines.extend(_render_checklist_item(item, before_sim=bsim))
        if len(items) > max_per_area:
            lines.append(f"- _… y {len(items) - max_per_area} ítem(s) más en esta sección._")
        lines.append("")

    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporte comparación diseño Lovable vs WEB")
    parser.add_argument("comparison_json", help="design-comparison.json")
    parser.add_argument("out_md", help="Ruta salida .md")
    parser.add_argument("run_id", nargs="?", default="local", help="ID del run CICD")
    parser.add_argument("--before", help="JSON comparación pre-agente (opcional, para delta post)")
    args = parser.parse_args()

    comparison = json.loads(Path(args.comparison_json).read_text(encoding="utf-8"))
    before = json.loads(Path(args.before).read_text(encoding="utf-8")) if args.before else None

    if not comparison.get("validationChecklist"):
        comparison["validationChecklist"] = build_validation_checklist(comparison)

    overall = comparison.get("overallSimilarityPercent", 0)
    target = comparison.get("targetSimilarityPercent", 98)
    gap = comparison.get("alignmentGapPercent", 0)
    summary = comparison.get("summary", {})
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    phase = _phase_label(args.run_id)

    lines = [
        "# Reporte — Comparación diseño Lovable vs DoEventsWEB",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| **Generado** | {ts} |",
        f"| **Run CICD** | {args.run_id} |",
        f"| **Fase** | {phase} |",
        f"| **Similitud global** | **{overall}%** |",
        f"| **Objetivo** | {target}% |",
        f"| **Brecha** | {gap}% |",
        f"| **Archivos rastreados** | {comparison.get('trackedFiles', 0)} |",
        f"| **Ítems QA pendientes** | {len(comparison.get('validationChecklist', []))} |",
        f"| **Requiere agente** | {comparison.get('requiresAgentForDesignAlignment', False)} |",
        "",
        "## Resumen numérico",
        "",
        f"- Alineados (≥98%): {summary.get('aligned', 0)}",
        f"- Deriva menor (85–97%): {summary.get('minorDrift', 0)}",
        f"- Requieren empalme (<85%): {summary.get('needsAdaptation', 0)}",
        f"- Ausentes en WEB: {summary.get('missingInWeb', 0)}",
        "",
    ]

    lines.extend(render_validation_section(comparison, before=before))

    lines.extend(
        [
            "## Detalle técnico — archivos con baja similitud",
            "",
        ]
    )

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
            f"_JSON fuente: `{Path(args.comparison_json).name}` — run {args.run_id}_",
        ]
    )

    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: {out} ({len(comparison.get('validationChecklist', []))} ítems QA)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
