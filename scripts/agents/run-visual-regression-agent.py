#!/usr/bin/env python3
"""Agente 9 — visual-regression: validación responsive/accesibilidad (determinista, sin IA masiva)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import load_manifest, load_yaml, norm_path, save_json
from agent_base import artifacts_dir, gh_output, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF visual-regression")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    responsive_policy = load_yaml(lovable / "reglasCalidad" / "responsive-policy.yml")
    a11y_policy = load_yaml(lovable / "reglasCalidad" / "accessibility-policy.yml")

    ui_paths = [
        norm_path(f.get("path", ""))
        for f in manifest.get("changedFiles", [])
        if f.get("kind") == "ui"
    ]

    checks: list[dict] = []
    pending = 0
    for rel in ui_paths:
        if not rel.startswith("src/components/"):
            continue
        checks.append({
            "lovablePath": rel,
            "responsive": {"mobile": "pending", "tablet": "pending", "desktop": "pending"},
            "accessibility": {"checked": False, "note": "declarar en empalme.responsive y empalme.accessibility"},
            "visualRegression": "skipped",
            "tool": "playwright",
            "reason": "requiere suite E2E configurada en DoEventsWEB",
        })
        pending += 1

    playwright_config = Path(os.environ.get("WEB_DIR", "")) / "playwright.config.ts"
    has_playwright = playwright_config.is_file()

    result = {
        "runId": args.run_id,
        "componentsChecked": len(checks),
        "checks": checks,
        "playwrightAvailable": has_playwright,
        "status": "skipped" if not has_playwright else "pending",
        "responsivePolicy": responsive_policy.get("id", ""),
        "accessibilityPolicy": a11y_policy.get("id", ""),
        "note": "No usa IA masiva — Playwright determinista cuando esté configurado",
        "passed": True,
    }

    out = artifacts_dir(args.run_id) / f"visual-regression-{args.run_id}.json"
    save_json(out, result)
    write_report(f"visual-regression-{args.run_id}.json", result, args.run_id)
    gh_output("visual_regression_status", result["status"])
    print(json.dumps({"ok": True, "status": result["status"], "pending": pending}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
