#!/usr/bin/env python3
"""Genera reporte de empalme de gaps: realizado, backend pendiente y gaps restantes."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from design_validation_hints import DEV_URL, build_validation_checklist, group_by_area

AGENT_DIR = "ReglasAgente"
TARGET_SIM = 98.0


def pending_gaps(comparison: dict) -> list[dict]:
    checklist = comparison.get("validationChecklist") or build_validation_checklist(comparison)
    gaps: list[dict] = []
    for item in checklist:
        status = item.get("status", "aligned")
        sim = float(item.get("similarityPercent", 0))
        if status == "aligned" or (status == "minor_drift" and sim >= TARGET_SIM):
            continue
        gaps.append(item)
    return gaps


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def parse_backend_table(impacto_md: str) -> list[dict]:
    rows: list[dict] = []
    in_table = False
    for line in impacto_md.splitlines():
        if "Backend pendiente para 100%" in line or "BACKEND_REQUIRED" in line and "|" in line:
            in_table = True
            continue
        if in_table and line.strip().startswith("|") and "---" not in line:
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) >= 4 and cols[0].lower() not in ("gap", "gap / feature", "feature"):
                rows.append(
                    {
                        "feature": cols[0],
                        "lovablePath": cols[1] if len(cols) > 1 else "",
                        "motivo": cols[3] if len(cols) > 3 else cols[2] if len(cols) > 2 else "",
                        "action": cols[-2] if len(cols) > 5 else "",
                        "priority": cols[-1] if len(cols) > 5 else "media",
                    }
                )
        elif in_table and line.strip() and not line.strip().startswith("|"):
            if line.startswith("#"):
                break
    return rows[:50]


def gaps_closed_in_batch(before: dict, after: dict, batch_paths: set[str]) -> list[dict]:
    before_map = {e["lovablePath"]: e for e in before.get("files") or []}
    after_map = {e["lovablePath"]: e for e in after.get("files") or []}
    closed: list[dict] = []
    for path in batch_paths:
        b = before_map.get(path, {})
        a = after_map.get(path, {})
        bsim = float(b.get("similarityPercent", 0))
        asim = float(a.get("similarityPercent", 0))
        bstatus = b.get("status", "missing_in_web")
        astatus = a.get("status", "aligned")
        improved = asim > bsim or (bstatus != "aligned" and astatus == "aligned") or asim >= 98
        closed.append(
            {
                "lovablePath": path,
                "webPath": a.get("webPath") or b.get("webPath", ""),
                "similarityBefore": bsim,
                "similarityAfter": asim,
                "statusBefore": bstatus,
                "statusAfter": astatus,
                "improved": improved,
            }
        )
    return closed


def render_gap_rows(gaps: list[dict], *, max_rows: int = 25) -> list[str]:
    lines: list[str] = []
    for g in gaps[:max_rows]:
        lines.append(
            f"| {g.get('feature', g.get('component', ''))} | {g.get('area', '')} | "
            f"`{g.get('lovablePath', '')}` | {g.get('status', '')} | {g.get('similarityPercent', 0)}% |"
        )
    if len(gaps) > max_rows:
        lines.append(f"| _… {len(gaps) - max_rows} más_ | | | | |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporte empalme de gaps")
    parser.add_argument("--before", required=True, help="design-comparison-before.json")
    parser.add_argument("--after", required=True, help="design-comparison-after.json")
    parser.add_argument("--manifest", required=True, help="gap-manifest.json")
    parser.add_argument("--web-dir", default="", help="DoEventsWEB para leer impacto-backend.md")
    parser.add_argument("--out", required=True, help="Reporte .md")
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    before = json.loads(Path(args.before).read_text(encoding="utf-8"))
    after = json.loads(Path(args.after).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    batch_paths = {g["lovablePath"] for g in manifest.get("gaps") or []}
    closed = gaps_closed_in_batch(before, after, batch_paths)
    improved_count = sum(1 for c in closed if c["improved"])

    remaining = pending_gaps(after)
    before_sim = before.get("overallSimilarityPercent", 0)
    after_sim = after.get("overallSimilarityPercent", 0)
    delta = round(after_sim - before_sim, 2)

    impacto = ""
    if args.web_dir:
        impacto_path = Path(args.web_dir) / AGENT_DIR / "impacto-backend.md"
        if impacto_path.exists():
            impacto = impacto_path.read_text(encoding="utf-8")

    backend_rows = parse_backend_table(impacto)

    lines = [
        f"# Reporte empalme de gaps — Run {args.run_id}",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Generado | {utc_now()} |",
        f"| Batch | {manifest.get('batchIndex', 1)} / {manifest.get('batchCount', 1)} |",
        f"| Gaps en batch | {manifest.get('gapsInBatch', 0)} |",
        f"| Entorno | [{DEV_URL}]({DEV_URL}) |",
        "",
        "## Resumen de similitud",
        "",
        "| Métrica | Antes | Después | Delta |",
        "|---------|-------|---------|-------|",
        f"| Similitud global | **{before_sim}%** | **{after_sim}%** | **{delta:+}%** |",
        f"| Gaps pendientes totales | {manifest.get('totalPendingGaps', 0)} | {len(remaining)} | {len(remaining) - manifest.get('totalPendingGaps', 0):+} |",
        f"| Gaps mejorados en batch | — | **{improved_count}** / {len(closed)} | — |",
        "",
        "## Empalme realizado (este batch)",
        "",
        "| Feature (Lovable) | WEB | Sim. antes | Sim. después | Mejoró |",
        "|-------------------|-----|------------|--------------|--------|",
    ]

    path_to_feature = {g["lovablePath"]: g.get("feature", "") for g in manifest.get("gaps") or []}
    for c in closed:
        feat = path_to_feature.get(c["lovablePath"], Path(c["lovablePath"]).stem)
        ok = "✅" if c["improved"] else "⚠️"
        lines.append(
            f"| {feat} | `{c.get('webPath', '—')}` | {c['similarityBefore']}% | "
            f"{c['similarityAfter']}% | {ok} |"
        )

    lines.extend(["", "## Backend pendiente para cerrar al 100%", ""])
    if backend_rows:
        lines.extend(
            [
                "| Gap / Feature | lovablePath | Motivo | Acción | Prioridad |",
                "|---------------|-------------|--------|--------|-----------|",
            ]
        )
        for row in backend_rows:
            lines.append(
                f"| {row.get('feature', '')} | `{row.get('lovablePath', '')}` | "
                f"{row.get('motivo', '')} | {row.get('action', '')} | {row.get('priority', '')} |"
            )
    else:
        lines.append(
            "_Sin entradas en `ReglasAgente/impacto-backend.md` — el agente debe documentar "
            "cada gap que no pueda cerrar sin backend._"
        )

    lines.extend(["", "## Gaps frontend aún pendientes", ""])
    if not remaining:
        lines.append("_Ninguno — diseño alineado al objetivo (≥98%)._")
    else:
        grouped = group_by_area(remaining[:80])
        for area, items in grouped.items():
            lines.append(f"### {area} ({len(items)})")
            lines.append("")
            lines.extend(render_gap_rows(items, max_rows=10))
            lines.append("")

    next_batch = manifest.get("remainingAfterBatch", 0)
    lines.extend(
        [
            "## Próximo paso",
            "",
        ]
    )
    if next_batch > 0 or len(remaining) > 0:
        lines.append(
            f"Quedan **{len(remaining)}** gap(s) frontend. Re-ejecutar workflow "
            f"`lovable-gap-empalme` con `batch_index={manifest.get('batchIndex', 1) + 1}` "
            f"(batch_size={manifest.get('batchSize', 20)})."
        )
    if backend_rows:
        lines.append(
            f"\nImplementar **{len(backend_rows)}** ítem(s) de backend documentados antes de "
            "marcar empalme al 100%."
        )
    if not remaining and not backend_rows:
        lines.append("Empalme completo — sin gaps frontend ni backend pendientes documentados.")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary_path = Path(args.out).resolve().parent.parent / f"gap-empalme-summary-{args.run_id}.json"
    summary_path.write_text(
        json.dumps(
            {
                "runId": args.run_id,
                "beforeSimilarity": before_sim,
                "afterSimilarity": after_sim,
                "deltaSimilarity": delta,
                "gapsImprovedInBatch": improved_count,
                "gapsRemaining": len(remaining),
                "backendPendingCount": len(backend_rows),
                "batchIndex": manifest.get("batchIndex", 1),
                "remainingAfterBatch": len(remaining),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"report": str(out), "gapsRemaining": len(remaining)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
