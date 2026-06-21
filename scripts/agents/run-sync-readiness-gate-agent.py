#!/usr/bin/env python3
"""Agente 2.5 — sync-readiness-gate: precondiciones antes de empalme."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import (
    changed_ui_paths,
    load_component_index,
    load_manifest,
    load_port_map_yml,
    load_yaml,
    norm_path,
    resolve_web_path,
    save_json,
)
from agent_base import artifacts_dir, gh_output, write_report

try:
    import yaml
except ImportError:
    yaml = None


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF sync-readiness-gate")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    ui_paths = changed_ui_paths(manifest)

    index = load_component_index(lovable)
    port_map = load_port_map_yml(lovable)
    checks: list[dict] = []
    failed = False

    for rel in ui_paths:
        in_index = rel in index
        in_port = rel in port_map
        web_path, status, meta = resolve_web_path(rel, lovable_root=lovable, web_root=web)
        has_rule = bool(meta.get("ruleId") or index.get(rel, {}).get("ruleId"))
        ok = in_index and in_port and bool(web_path) and has_rule and status not in ("blocked",)
        if not ok:
            failed = True
        checks.append({
            "lovablePath": rel,
            "inComponentIndex": in_index,
            "inPortMap": in_port,
            "webPathResolved": bool(web_path),
            "hasRuleId": has_rule,
            "status": status,
            "ready": ok,
        })

    # Estructura mínima repo
    required_dirs = [
        "reglasEmpalme/schema-capas.yml",
        "reglasEmpalme/routing-agentes.yml",
        "reglasEmpalme/component-index.yml",
        "reglasEmpalme/port-map.yml",
        "reglasCalidad/risk-policy.yml",
        "reglasRelease/feature-flags.yml",
        "reglasRelease/compatibility-policy.yml",
        "contratosBackend/endpoints.yml",
    ]
    structure_ok = all((lovable / p).is_file() for p in required_dirs)
    if not structure_ok:
        failed = True

    coverage = 100.0 if not ui_paths else round(100 * sum(1 for c in checks if c["ready"]) / len(ui_paths), 1)

    result = {
        "runId": args.run_id,
        "syncReadiness": {
            "componentIndexCoverage": coverage,
            "structureComplete": structure_ok,
            "allPathsReady": not failed,
            "checks": checks,
        },
        "riskLevel": "blocked" if failed else "low",
        "requiresManualReview": failed,
        "passed": not failed,
    }

    out = artifacts_dir(args.run_id) / f"sync-readiness-gate-{args.run_id}.json"
    save_json(out, result)
    write_report(f"sync-readiness-gate-{args.run_id}.json", result, args.run_id)
    gh_output("sync_readiness_passed", str(not failed).lower())
    print(json.dumps({"ok": not failed, "coverage": coverage, "uiFiles": len(ui_paths)}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
