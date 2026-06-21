#!/usr/bin/env python3
"""Reporte unificado empalme DSF — aplicado, manual, cursor, backend."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from design_validation_hints import DEV_URL, build_validation_checklist, group_by_area


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def file_delta(before: dict, after: dict) -> list[dict]:
    bmap = {e["lovablePath"]: e for e in before.get("files") or []}
    amap = {e["lovablePath"]: e for e in after.get("files") or []}
    rows: list[dict] = []
    for path in sorted(set(bmap) | set(amap)):
        b = bmap.get(path, {})
        a = amap.get(path, {})
        bsim = float(b.get("similarityPercent", 0))
        asim = float(a.get("similarityPercent", 0))
        if abs(asim - bsim) < 0.01 and b.get("status") == a.get("status"):
            continue
        rows.append({
            "lovablePath": path,
            "webPath": a.get("webPath") or b.get("webPath", ""),
            "similarityBefore": bsim,
            "similarityAfter": asim,
            "delta": round(asim - bsim, 2),
            "statusBefore": b.get("status", ""),
            "statusAfter": a.get("status", ""),
        })
    rows.sort(key=lambda r: -abs(r["delta"]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--python-result", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-json", required=True)
    args = parser.parse_args()

    before = load(args.before)
    after = load(args.after)
    py = load(args.python_result)
    summary = load(args.summary)

    deltas = file_delta(before, after)
    remaining = build_validation_checklist(after)
    remaining = [
        g for g in remaining
        if g.get("status") not in ("aligned",) and float(g.get("similarityPercent", 0)) < 98
    ]

    report = {
        "generatedAt": utc_now(),
        "devUrl": DEV_URL,
        "summary": summary,
        "similarityBefore": before.get("overallSimilarityPercent"),
        "similarityAfter": after.get("overallSimilarityPercent"),
        "pythonEmpalme": {
            "applied": py.get("applied", []),
            "skipped": py.get("skipped", []),
            "cursorRequired": py.get("cursorRequired", []),
            "manualRequired": py.get("manualRequired", []),
            "backendRequired": py.get("backendRequired", []),
        },
        "fileDeltas": deltas[:80],
        "remainingGaps": remaining[:100],
        "remainingByArea": {k: len(v) for k, v in group_by_area(remaining).items()},
    }

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Reporte empalme DSF — {summary.get('runId', 'local')}",
        "",
        f"**Generado:** {utc_now()}",
        f"**DEV:** {DEV_URL}",
        "",
        "## Resumen",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Similitud antes | {report['similarityBefore']}% |",
        f"| Similitud después | {report['similarityAfter']}% |",
        f"| Delta | {summary.get('similarityDelta', 0)}% |",
        f"| Aplicado (Python) | {summary.get('pythonApplied', 0)} archivos |",
        f"| Escalado Cursor | {'Sí' if summary.get('cursorEscalationUsed') else 'No'} |",
        f"| Pendiente manual | {summary.get('manualRequired', 0)} |",
        f"| Pendiente backend | {summary.get('backendRequired', 0)} |",
        f"| Gaps restantes | {len(remaining)} |",
        "",
        "## Ajustes aplicados (Python)",
        "",
    ]
    applied = py.get("applied") or []
    if applied:
        lines.append("| Lovable | WEB | Motivo |")
        lines.append("|---------|-----|--------|")
        for a in applied:
            lines.append(
                f"| `{a.get('lovablePath','')}` | `{a.get('webPath','')}` | {a.get('reason','')} |"
            )
    else:
        lines.append("_Sin cambios aplicados en esta ejecución (diff vacío o dry-run)._")

    lines.extend(["", "## Escalar a Cursor (refuerzo puntual, sin loop)", ""])
    cursor_req = py.get("cursorRequired") or []
    if cursor_req:
        lines.append("| Lovable | WEB | Sim % | Motivo |")
        lines.append("|---------|-----|-------|--------|")
        for c in cursor_req:
            lines.append(
                f"| `{c.get('lovablePath','')}` | `{c.get('webPath','')}` | "
                f"{c.get('similarityPercent',0)}% | {c.get('reason','')} |"
            )
    else:
        lines.append("_Nada pendiente para Cursor en este diff._")

    lines.extend(["", "## Ajustar a mano", ""])
    manual = py.get("manualRequired") or []
    if manual:
        for m in manual[:30]:
            lines.append(f"- `{m.get('lovablePath','')}` — {m.get('reason','')}")
    else:
        lines.append("_Nada clasificado como manual en este diff._")

    lines.extend(["", "## Backend requerido", ""])
    backend = py.get("backendRequired") or []
    if backend:
        for b in backend[:20]:
            lines.append(f"- `{b.get('lovablePath','')}` — {b.get('reason','')}")
    else:
        lines.append("_Nada clasificado como backend en este diff._")

    lines.extend(["", "## Mejoras por archivo (delta similitud)", ""])
    if deltas:
        lines.append("| Lovable | Antes | Después | Δ |")
        lines.append("|---------|-------|---------|---|")
        for d in deltas[:25]:
            lines.append(
                f"| `{d['lovablePath']}` | {d['similarityBefore']}% | "
                f"{d['similarityAfter']}% | {d['delta']:+.2f}% |"
            )

    lines.extend(["", "## Gaps restantes por área", ""])
    for area, count in sorted(report["remainingByArea"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{area}:** {count}")

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "md": args.out_md, "json": args.out_json}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
