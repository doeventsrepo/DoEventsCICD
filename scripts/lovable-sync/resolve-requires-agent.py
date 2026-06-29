#!/usr/bin/env python3
"""Resuelve si adapt es obligatorio según manifiesto + dsf.properties."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD_ROOT))

from dsf.sync_policy import load_sync_policy, resolve_requires_agent  # noqa: E402


def gh_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF — requires_agent desde syncPolicy")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--design", default="")
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--target-sim", type=float, default=98.0)
    args = parser.parse_args()

    cicd = Path(args.cicd_dir).resolve()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    design = json.loads(Path(args.design).read_text(encoding="utf-8")) if args.design and Path(args.design).is_file() else {}

    policy = load_sync_policy(cicd)
    requires = resolve_requires_agent(manifest, design, policy, target_similarity=args.target_sim)

    out = {
        "requiresAgent": requires,
        "syncPolicy": policy,
        "hasUiChanges": manifest.get("hasUiChanges"),
        "hasRulesChanges": manifest.get("hasRulesChanges"),
        "overallSimilarityPercent": design.get("overallSimilarityPercent"),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    gh_output("requires_agent", str(requires).lower())
    return 0


if __name__ == "__main__":
    sys.exit(main())
