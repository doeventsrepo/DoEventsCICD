#!/usr/bin/env python3
"""Construye manifiesto de gaps pendientes para empalme focalizado."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from design_validation_hints import build_validation_checklist

PRIORITY = {"missing_in_web": 0, "needs_adaptation": 1, "minor_drift": 2, "aligned": 3}
TARGET_SIM = 98.0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def pending_gaps(comparison: dict, *, area_filter: str = "") -> list[dict]:
    checklist = comparison.get("validationChecklist") or build_validation_checklist(comparison)
    gaps: list[dict] = []
    for item in checklist:
        status = item.get("status", "aligned")
        sim = float(item.get("similarityPercent", 0))
        if status == "aligned" or (status == "minor_drift" and sim >= TARGET_SIM):
            continue
        if area_filter and item.get("area") != area_filter:
            continue
        gaps.append(
            {
                "lovablePath": item.get("lovablePath", ""),
                "webPath": _web_path(comparison, item.get("lovablePath", "")),
                "status": status,
                "similarityPercent": sim,
                "area": item.get("area", "Otros"),
                "feature": item.get("feature", ""),
                "where": item.get("where", ""),
                "action": item.get("action", ""),
                "checks": item.get("checks") or [],
                "component": item.get("component", ""),
            }
        )

    gaps.sort(
        key=lambda g: (
            PRIORITY.get(g["status"], 9),
            -g.get("similarityPercent", 0),
        )
    )
    return gaps


def _web_path(comparison: dict, lovable_path: str) -> str:
    for entry in comparison.get("files") or []:
        if entry.get("lovablePath") == lovable_path:
            return entry.get("webPath", "")
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Manifiesto de gaps Lovable vs WEB")
    parser.add_argument("comparison_json", help="design-comparison.json")
    parser.add_argument("out_json", help="gap-manifest.json")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--batch-index", type=int, default=1, help="1-based batch number")
    parser.add_argument("--area", default="", help="Filtrar por área (ej. Autenticación)")
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    comparison = json.loads(Path(args.comparison_json).read_text(encoding="utf-8"))
    all_gaps = pending_gaps(comparison, area_filter=args.area.strip())
    batch_size = max(1, args.batch_size)
    start = (args.batch_index - 1) * batch_size
    batch = all_gaps[start : start + batch_size]

    manifest = {
        "version": "1.0",
        "purpose": "Gaps pendientes para empalme focalizado Lovable → DoEventsWEB",
        "generatedAt": utc_now(),
        "workflowRunId": args.run_id,
        "beforeSimilarityPercent": comparison.get("overallSimilarityPercent", 0),
        "targetSimilarityPercent": comparison.get("targetSimilarityPercent", TARGET_SIM),
        "alignmentGapPercent": comparison.get("alignmentGapPercent", 0),
        "totalPendingGaps": len(all_gaps),
        "batchSize": batch_size,
        "batchIndex": args.batch_index,
        "batchCount": max(1, (len(all_gaps) + batch_size - 1) // batch_size) if all_gaps else 0,
        "gapsInBatch": len(batch),
        "remainingAfterBatch": max(0, len(all_gaps) - start - len(batch)),
        "areaFilter": args.area or None,
        "gaps": batch,
        "allPendingPaths": [g["lovablePath"] for g in all_gaps],
    }

    out = Path(args.out_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        json.dumps(
            {
                "totalPendingGaps": len(all_gaps),
                "gapsInBatch": len(batch),
                "remainingAfterBatch": manifest["remainingAfterBatch"],
                "hasGaps": len(batch) > 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
