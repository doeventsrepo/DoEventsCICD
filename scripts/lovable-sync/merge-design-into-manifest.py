#!/usr/bin/env python3
"""Fusiona design-comparison.json en lovable-change-manifest.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD_ROOT))

from dsf.sync_policy import load_sync_policy  # noqa: E402

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
        print("Uso: merge-design-into-manifest.py <manifest.json> <design-comparison.json> [copy_to] [cicd-dir]", file=sys.stderr)
        return 1

    manifest_path = Path(sys.argv[1])
    design_path = Path(sys.argv[2])
    cicd_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else CICD_ROOT
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    design = json.loads(design_path.read_text(encoding="utf-8"))

    policy = load_sync_policy(cicd_dir)
    manifest["designComparison"] = {k: design[k] for k in KEYS if k in design}
    manifest["syncPolicy"] = policy

    if policy.get("designComparisonInformational"):
        # requiresAgent solo desde diff git (analyze-lovable-diff), no similitud global
        manifest["requiresAgent"] = bool(
            manifest.get("hasUiChanges") or manifest.get("hasRulesChanges")
        )
    else:
        manifest["requiresAgent"] = bool(
            manifest.get("requiresAgent", False)
            or design.get("requiresAgentForDesignAlignment", False)
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
