#!/usr/bin/env python3
"""Agente 6.5 — release-guard: feature flags + backward compatibility."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import changed_ui_paths, load_component_index, load_manifest, load_yaml, save_json
from agent_base import artifacts_dir, gh_output, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF release-guard")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    ui_paths = changed_ui_paths(manifest)
    flags_doc = load_yaml(lovable / "reglasRelease" / "feature-flags.yml")
    compat_doc = load_yaml(lovable / "reglasRelease" / "compatibility-policy.yml")
    index = load_component_index(lovable)

    findings: list[dict] = []
    blocked = False

    for rel in ui_paths:
        entry = index.get(rel, {})
        ff = entry.get("featureFlag") or {}
        bc = entry.get("backwardCompatibility") or {}
        if ff.get("required") and not ff.get("flagName"):
            findings.append({"lovablePath": rel, "issue": "featureFlag.required sin flagName", "riskLevel": "blocked"})
            blocked = True
        impact = str(bc.get("impact", "none")).lower()
        if impact == "breaking" and bc.get("requiresManualReview", True):
            findings.append({"lovablePath": rel, "issue": "backwardCompatibility breaking", "riskLevel": "high"})

    policy = compat_doc.get("backwardCompatibilityPolicy") or {}
    if policy.get("breakingChangesBlocked") and any(
        str((index.get(p) or {}).get("backwardCompatibility", {}).get("impact", "")).lower() == "breaking"
        for p in ui_paths
    ):
        blocked = True

    result = {
        "runId": args.run_id,
        "featureFlagsPolicy": flags_doc.get("id", ""),
        "compatibilityPolicy": compat_doc.get("id", ""),
        "findings": findings,
        "riskLevel": "blocked" if blocked else ("high" if findings else "low"),
        "requiresManualReview": blocked or bool(findings),
        "passed": not blocked,
    }

    out = artifacts_dir(args.run_id) / f"release-guard-{args.run_id}.json"
    save_json(out, result)
    write_report(f"release-guard-{args.run_id}.json", result, args.run_id)
    gh_output("release_guard_passed", str(not blocked).lower())
    print(json.dumps({"ok": not blocked, "findings": len(findings)}, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
