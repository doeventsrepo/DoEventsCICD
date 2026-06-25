#!/usr/bin/env python3
"""
BSF — Orquestador Backend Sync Framework.

Pipeline portable: detectar delta FE→BE → contratos → implementar (Cursor) →
acoplamiento → deploy DEV → healer → reporte.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).resolve().parent
CICD_ROOT = AGENTS_DIR.parents[1]
LOVABLE_SYNC = CICD_ROOT / "scripts" / "lovable-sync"
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(LOVABLE_SYNC))

from agent_base import artifacts_dir, cicd_root, gh_output, is_dry_run, is_local_mode, load_config, write_report

BSF_STEPS = [
    "detect-delta",
    "contract-check",
    "implement",
    "coupling",
    "deploy",
    "healer",
    "report",
]


def run_script(rel: str, extra: list[str], env: dict | None = None) -> dict[str, Any]:
    script = CICD_ROOT / rel
    if not script.is_file():
        return {"ok": False, "error": f"no existe {script}"}
    proc = subprocess.run(
        [sys.executable, str(script), *extra],
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=7200,
    )
    return {
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "stdout": (proc.stdout or "")[-3000:],
        "stderr": (proc.stderr or "")[-1500:],
    }


def load_delta(run_id: str) -> dict[str, Any]:
    p = artifacts_dir(run_id) / f"backend-delta-{run_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF backend-sync orchestrator")
    parser.add_argument("--lovable-dir", default=os.environ.get("LOVABLE_DIR", ""))
    parser.add_argument("--web-dir", default=os.environ.get("WEB_DIR", ""))
    parser.add_argument("--back-dir", default=os.environ.get("BACK_DIR", ""))
    parser.add_argument("--cicd-dir", default=os.environ.get("CICD_DIR", str(CICD_ROOT)))
    parser.add_argument("--change-manifest", default=os.environ.get("DSF_CHANGE_MANIFEST", ""))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", f"bsf-{int(time.time())}"))
    parser.add_argument("--skip-deploy", action="store_true")
    parser.add_argument("--skip-implement", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DSF_AGENT_DRY_RUN"] = "1"
        os.environ.setdefault("DSF_LOCAL_MODE", "1")

    cfg = load_config()
    app_root = Path(args.cicd_dir).resolve().parent
    if not args.lovable_dir:
        args.lovable_dir = str(app_root / "discover-joyful-feed")
    if not args.web_dir:
        args.web_dir = str(app_root / "DoEventsWEB")
    if not args.back_dir:
        args.back_dir = str(app_root / "DoEventsBack")

    manifest = Path(args.change_manifest) if args.change_manifest else None
    if not manifest or not manifest.is_file():
        for c in (
            Path(args.cicd_dir) / "lovable-change-manifest.json",
            Path(args.lovable_dir) / "lovable-change-manifest.json",
        ):
            if c.is_file():
                manifest = c
                break
    if not manifest or not manifest.is_file():
        manifest = Path(args.cicd_dir) / "lovable-change-manifest.json"

    os.environ.update({
        "CICD_DIR": args.cicd_dir,
        "LOVABLE_DIR": args.lovable_dir,
        "WEB_DIR": args.web_dir,
        "BACK_DIR": args.back_dir,
        "GITHUB_RUN_ID": args.run_id,
        "DSF_LOCAL_RUN_ID": args.run_id,
        "DSF_CHANGE_MANIFEST": str(manifest),
    })

    common = [
        "--lovable-dir", args.lovable_dir,
        "--web-dir", args.web_dir,
        "--change-manifest", str(manifest),
        "--run-id", args.run_id,
    ]

    results: list[dict[str, Any]] = []
    rc = 0

    # 1 — Delta
    r = run_script("scripts/lovable-sync/detect-frontend-backend-delta.py", common)
    results.append({"step": "detect-delta", **r})
    delta = load_delta(args.run_id)
    requires = delta.get("requiresBackendCount", 0) > 0

    # 2 — Contract check
    r = run_script("scripts/agents/run-backend-contract-check-agent.py", [
        "--lovable-dir", args.lovable_dir,
        "--change-manifest", str(manifest),
        "--run-id", args.run_id,
    ])
    results.append({"step": "contract-check", **r})
    if not r["ok"] and not is_dry_run():
        rc = 1

    # 3 — Implement (Cursor API → DoEventsBack)
    if requires and not args.skip_implement:
        r = run_script("scripts/agents/run-backend-implement-agent.py", [
            "--web-dir", args.web_dir,
            "--back-dir", args.back_dir,
            "--run-id", args.run_id,
            "--delta-json", str(artifacts_dir(args.run_id) / f"backend-delta-{args.run_id}.json"),
        ])
        results.append({"step": "implement", **r})
        if not r["ok"] and not is_dry_run():
            rc = max(rc, 1)

    # 4 — Coupling
    r = run_script("scripts/lovable-sync/analyze-backend-coupling.py", common)
    results.append({"step": "coupling", **r})

    # 5 — Deploy selective lambdas DEV
    if requires and not args.skip_deploy and not is_dry_run():
        lambda_dirs = ",".join(delta.get("lambdaDirsToDeploy") or [])
        if lambda_dirs:
            deploy_ps = CICD_ROOT / "scripts" / "deploy" / "deploy-back-dev.ps1"
            if deploy_ps.is_file():
                proc = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(deploy_ps),
                        "-LambdaDirs", lambda_dirs,
                        "-BackRoot", args.back_dir,
                        "-RunId", args.run_id,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=3600,
                )
                deploy_result = {
                    "ok": proc.returncode == 0,
                    "exitCode": proc.returncode,
                    "stdout": (proc.stdout or "")[-2000:],
                    "stderr": (proc.stderr or "")[-1000:],
                }
            else:
                deploy_result = {"ok": False, "error": "deploy-back-dev.ps1 no encontrado"}
            results.append({"step": "deploy", **deploy_result})
            if not deploy_result["ok"]:
                rc = max(rc, 1)

    # 6 — Error healer (lee JSONL y escala a Cursor si hay errores)
    r = run_script("scripts/agents/run-backend-error-healer-agent.py", [
        "--back-dir", args.back_dir,
        "--run-id", args.run_id,
    ])
    results.append({"step": "healer", **r})

    # 7 — Reporte markdown
    r = run_script("scripts/lovable-sync/generate-backend-sync-report.py", [
        "--cicd-dir", args.cicd_dir,
        "--run-id", args.run_id,
    ])
    results.append({"step": "report", **r})

    coupling_path = artifacts_dir(args.run_id) / f"backend-coupling-{args.run_id}.json"
    coupling = json.loads(coupling_path.read_text(encoding="utf-8")) if coupling_path.is_file() else {}

    summary = {
        "runId": args.run_id,
        "framework": "BSF v1.0",
        "requiresBackend": requires,
        "domainsAffected": delta.get("domainsAffected") or [],
        "couplingPercent": coupling.get("overallCouplingPercent"),
        "steps": results,
        "ok": all(s.get("ok", True) for s in results if s.get("step") not in ("healer",)),
        "dryRun": is_dry_run() or is_local_mode(),
        "backendBranch": cfg.get("branches", {}).get("cicdBack", "feature/cicd/dev-automation"),
        "backendRepo": cfg.get("repositories", {}).get("backend"),
    }
    write_report(f"backend-sync-summary-{args.run_id}.json", summary, args.run_id)
    gh_output("backend_sync_ok", str(summary["ok"]).lower())
    gh_output("backend_coupling_percent", str(coupling.get("overallCouplingPercent", 0)))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] or is_dry_run() else rc


if __name__ == "__main__":
    sys.exit(main())
