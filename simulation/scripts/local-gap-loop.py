#!/usr/bin/env python3
"""Gap loop 100% local — empalme en sandbox, sin GitHub ni Cursor API."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SIM_SCRIPTS = Path(__file__).resolve().parent
CICD_SCRIPTS = SIM_SCRIPTS.parent.parent / "scripts" / "lovable-sync"


def run(cmd: list[str]) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd).returncode


def similarity(path: Path) -> float:
    return float(json.loads(path.read_text(encoding="utf-8"))["overallSimilarityPercent"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Gap loop local (sin GitHub)")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--comparison", required=True, help="design-comparison.json inicial")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--target", type=float, default=98.0)
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-items", type=int, default=120)
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    port_map = Path(args.port_map).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    compare_py = CICD_SCRIPTS / "compare-design-similarity.py"
    empalme_py = SIM_SCRIPTS / "local-apply-empalme.py"
    comparison = Path(args.comparison).resolve()

    current = similarity(comparison)
    print(json.dumps({"initialSimilarity": current, "target": args.target, "mode": "local-only"}, indent=2))

    if current >= args.target:
        summary = {"ok": True, "mode": "local-only", "finalSimilarity": current, "rounds": 0}
        (out_dir / "gap-loop-summary-local.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return 0

    for round_idx in range(1, args.max_rounds + 1):
        report = out_dir / f"local-empalme-round-{round_idx}.json"
        rc = run(
            [
                sys.executable,
                str(empalme_py),
                "--lovable-dir",
                str(lovable),
                "--web-dir",
                str(web),
                "--comparison",
                str(comparison),
                "--min-sim",
                str(args.target),
                "--max-items",
                str(args.max_items),
                "--out",
                str(report),
            ]
        )
        if rc != 0:
            return rc

        after = out_dir / f"design-comparison-round-{round_idx}.json"
        rc = run(
            [
                sys.executable,
                str(compare_py),
                str(lovable),
                str(web),
                str(port_map),
                str(after),
            ]
        )
        if rc != 0:
            return rc

        current = similarity(after)
        comparison = after
        print(json.dumps({"round": round_idx, "similarity": current}, indent=2))
        if current >= args.target:
            break

    summary = {
        "ok": current >= args.target,
        "mode": "local-only",
        "finalSimilarity": current,
        "target": args.target,
        "rounds": round_idx,
        "githubContact": False,
    }
    (out_dir / "gap-loop-summary-local.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "design-comparison-gap-final.json").write_text(comparison.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
