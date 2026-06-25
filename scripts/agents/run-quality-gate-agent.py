#!/usr/bin/env python3
"""Agente 8 — quality-gate: lint, typecheck, build, forbidden patterns."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
CICD_ROOT = AGENTS_DIR.parents[1]
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import save_json
from agent_base import artifacts_dir, gh_output, is_dry_run, write_report


def run_cmd(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
        return proc.returncode, (proc.stdout or "")[-500:] + (proc.stderr or "")[-500:]
    except Exception as exc:
        return 1, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF quality-gate")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    cicd = Path(args.cicd_dir).resolve()
    checks: dict[str, dict] = {}
    failed = False

    validators = [
        ([sys.executable, str(cicd / "scripts/lovable-sync/validate-empalme-rules.py"), str(lovable)], "empalme_rules"),
        ([sys.executable, str(cicd / "scripts/lovable-sync/validate-calidad-rules.py"), str(lovable)], "calidad_rules"),
    ]
    for cmd, name in validators:
        rc, out = run_cmd(cmd, cicd)
        checks[name] = {"ok": rc == 0, "exitCode": rc, "note": out[-200:] if rc else "ok"}
        if rc != 0 and not is_dry_run():
            failed = True
        elif rc != 0 and is_dry_run():
            checks[name]["warnOnly"] = True

    mock_script = cicd / "scripts/lovable-sync/validate-no-mocks.sh"
    if mock_script.is_file() and not is_dry_run():
        rc, out = run_cmd(["bash", str(mock_script), str(web)], cicd)
        checks["no_mocks"] = {"ok": rc == 0, "exitCode": rc}
        if rc != 0:
            failed = True
    elif is_dry_run():
        checks["no_mocks"] = {"ok": True, "skipped": True, "reason": "dry-run"}

    if not args.skip_build and not is_dry_run() and (web / "package.json").is_file():
        for name, cmd in [
            ("lint", ["npm", "run", "lint"]),
            ("typecheck", ["npm", "run", "typecheck"]),
            ("build", ["npm", "run", "build:devaws"]),
        ]:
            rc, out = run_cmd(cmd, web)
            checks[name] = {"ok": rc == 0, "exitCode": rc, "note": out[-200:] if rc else "ok"}
            if rc != 0 and name in ("build", "typecheck"):
                failed = True
    else:
        checks["lint"] = {"ok": True, "skipped": True}
        checks["typecheck"] = {"ok": True, "skipped": True}
        checks["build"] = {"ok": True, "skipped": args.skip_build or is_dry_run()}

    result = {
        "runId": args.run_id,
        "checks": checks,
        "passed": not failed,
        "riskLevel": "blocked" if failed else "low",
    }

    out = artifacts_dir(args.run_id) / f"quality-gate-{args.run_id}.json"
    save_json(out, result)
    write_report(f"quality-gate-{args.run_id}.json", result, args.run_id)
    gh_output("quality_gate_passed", str(not failed).lower())
    print(json.dumps({"ok": not failed, "checks": list(checks.keys())}, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
