#!/usr/bin/env python3
"""Agente 4.5 — anti-regression-guard: valida resultado empalme Python (delta-only)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
CICD_ROOT = AGENTS_DIR.parents[1]
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from agent_base import artifacts_dir, gh_output, write_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF anti-regression-guard")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--python-result", default="", help="empalme-python-result JSON")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    cicd = Path(args.cicd_dir).resolve()
    result_path = Path(args.python_result) if args.python_result else (
        cicd / f"empalme-python-result-{args.run_id}.json"
    )
    if not result_path.is_file():
        alt = artifacts_dir(args.run_id) / f"empalme-python-result-{args.run_id}.json"
        result_path = alt if alt.is_file() else result_path

    if not result_path.is_file():
        out = {
            "runId": args.run_id,
            "status": "skipped",
            "reason": "sin_resultado_python_empalme",
            "passed": True,
        }
        write_report(f"anti-regression-guard-{args.run_id}.json", out, args.run_id)
        gh_output("anti_regression_status", "skipped")
        print(json.dumps(out, indent=2))
        return 0

    data = json.loads(result_path.read_text(encoding="utf-8"))
    cursor_items = data.get("cursorRequired") or []
    regression_items = [
        c for c in cursor_items
        if "anti_regression" in c.get("reason", "") or "delta_incompleto" in c.get("reason", "")
    ]
    applied = data.get("applied") or []
    delta_applied = [a for a in applied if a.get("applyMode") == "delta"]
    full_applied = [a for a in applied if a.get("applyMode") == "full"]

    violations: list[str] = []
    if full_applied:
        for item in full_applied:
            wp = item.get("webPath", "")
            if wp and (Path(args.web_dir) / wp).is_file():
                violations.append(f"full_replace_sobre_existente:{wp}")

    if regression_items:
        for item in regression_items[:5]:
            violations.append(f"{item.get('lovablePath')}: {item.get('reason', '')[:120]}")

    passed = len(violations) == 0
    out = {
        "runId": args.run_id,
        "status": "passed" if passed else "blocked",
        "passed": passed,
        "deltaAppliedCount": len(delta_applied),
        "fullAppliedCount": len(full_applied),
        "regressionEscalations": len(regression_items),
        "violations": violations,
    }
    write_report(f"anti-regression-guard-{args.run_id}.json", out, args.run_id)
    gh_output("anti_regression_status", out["status"])
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
