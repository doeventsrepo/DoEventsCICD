#!/usr/bin/env python3
"""Fusiona design-comparison.json en lovable-change-manifest.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

KEYS = (
    "overallSimilarityPercent",
    "targetSimilarityPercent",
    "alignmentGapPercent",
    "missingInWebCount",
    "needsAdaptationCount",
    "requiresAgentForDesignAlignment",
    "missingInWeb",
    "lowSimilarity",
    "summary",
    "trackedFiles",
)


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: merge-design-into-manifest.py <manifest.json> <design-comparison.json> [copy_to]", file=sys.stderr)
        return 1

    manifest_path = Path(sys.argv[1])
    design_path = Path(sys.argv[2])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads(design_path.read_text(encoding="utf-8"))

    manifest["designComparison"] = {k: design[k] for k in KEYS if k in design}
    manifest["requiresAgent"] = bool(
        manifest.get("requiresAgent", False) or design.get("requiresAgentForDesignAlignment", False)
    )

    text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    manifest_path.write_text(text, encoding="utf-8")
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(text, encoding="utf-8")

    out = {
        "requiresAgent": manifest["requiresAgent"],
        "overallSimilarityPercent": design.get("overallSimilarityPercent"),
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
