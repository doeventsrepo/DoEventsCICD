#!/usr/bin/env python3
"""Recalcula similitud global tras corrección port-map (sin re-leer todos los archivos)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CICD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD / "scripts" / "lovable-sync"))
from port_map_utils import load_port_map, map_lovable_to_web, mapping_for  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_in")
    parser.add_argument("comparison_out")
    parser.add_argument("--port-map", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.comparison_in).read_text(encoding="utf-8"))
    items = load_port_map(Path(args.port_map))
    total = 0.0
    tracked = 0
    low: list[dict] = []

    for entry in data.get("files") or []:
        rel = entry.get("lovablePath", "")
        web_rel = map_lovable_to_web(rel, items) or entry.get("webPath", "")
        meta = mapping_for(rel, items) or {}
        entry["webPath"] = web_rel

        if meta.get("compareMode") == "delegated" or "mfe-auth" in web_rel.replace("\\", "/"):
            entry["similarityPercent"] = 100.0
            entry["status"] = "aligned"
            entry["compareMode"] = "delegated"
            entry["action"] = "none"
            ratio = 1.0
        else:
            ratio = float(entry.get("similarityPercent", 0)) / 100.0
            pct = float(entry.get("similarityPercent", 0))
            if pct < 85:
                entry["status"] = "needs_adaptation"
                low.append({"lovablePath": rel, "webPath": web_rel, "similarityPercent": pct})
            elif pct < 98:
                entry["status"] = "minor_drift"
            else:
                entry["status"] = "aligned"

        total += ratio
        tracked += 1

    overall = round((total / tracked * 100) if tracked else 100.0, 2)
    data["overallSimilarityPercent"] = overall
    data["alignmentGapPercent"] = round(max(0.0, 98.0 - overall), 2)
    data["requiresAgentForDesignAlignment"] = overall < 98.0 or len(low) > 0
    data["needsAdaptationCount"] = len(low)
    data["lowSimilarity"] = low[:50]
    data["summary"] = {
        "aligned": sum(1 for e in data["files"] if e.get("status") == "aligned"),
        "minorDrift": sum(1 for e in data["files"] if e.get("status") == "minor_drift"),
        "needsAdaptation": sum(1 for e in data["files"] if e.get("status") == "needs_adaptation"),
        "missingInWeb": sum(1 for e in data["files"] if e.get("status") == "missing_in_web"),
    }
    data["version"] = "1.2"
    out = Path(args.comparison_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps({"overallSimilarityPercent": overall, "requiresAgent": data["requiresAgentForDesignAlignment"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
