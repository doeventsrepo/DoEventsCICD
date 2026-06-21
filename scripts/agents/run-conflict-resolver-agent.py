#!/usr/bin/env python3
"""Agente 2.7 — conflict-resolver: jerarquía de verdad DSF."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_conflicts import TRUTH_HIERARCHY, detect_conflicts, has_blocking_conflicts
from dsf_shared import changed_ui_paths, load_manifest, save_json
from agent_base import artifacts_dir, gh_output, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF conflict-resolver")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", default="")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    ui_paths: list[str] = []
    if args.change_manifest and Path(args.change_manifest).is_file():
        ui_paths = changed_ui_paths(load_manifest(Path(args.change_manifest)))

    conflicts = detect_conflicts(lovable, web, ui_paths or None)
    blocked = has_blocking_conflicts(conflicts)

    result = {
        "runId": args.run_id,
        "truthHierarchy": TRUTH_HIERARCHY,
        "conflictCount": len(conflicts),
        "blockingCount": sum(1 for c in conflicts if c.get("resolution") == "blocked"),
        "conflicts": conflicts,
        "riskLevel": "blocked" if blocked else ("medium" if conflicts else "low"),
        "requiresManualReview": blocked or bool(conflicts),
        "passed": not blocked,
        "decision": "blocked" if blocked else ("manual-review" if conflicts else "approved"),
    }

    out = artifacts_dir(args.run_id) / f"conflict-resolver-{args.run_id}.json"
    save_json(out, result)
    write_report(f"conflict-resolver-{args.run_id}.json", result, args.run_id)
    gh_output("conflict_resolver_passed", str(not blocked).lower())
    print(json.dumps({"ok": not blocked, "conflicts": len(conflicts), "decision": result["decision"]}, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
