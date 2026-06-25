#!/usr/bin/env python3
"""
Orquestador DSF v1.1 — pipeline 17 pasos, python-first, sin gap-loops.

0 diff-intelligence → 1 rules-validation → 2 port-map-resolver → 2.3 idempotency-guard
→ 2.7 conflict-resolver → 2.5 sync-readiness-gate
→ 3 rules-refinement → 4 python-empalme (+7 cursor) → 5 dependency-guard
→ 6 backend-contract-check → 6.x BSF backend-sync → 6.5 release-guard → 8 quality-gate
→ 9 visual-regression → 10 premerge-review → 11 backend-analysis → 14 report-generator
(12 deploy-dev, 13 smoke — CI)
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
sys.path.insert(0, str(AGENTS_DIR))

from agent_base import artifacts_dir, gh_output, is_dry_run, load_config, write_report  # noqa: E402

PHASE_AGENTS: dict[str, list[str]] = {
    "pre-adapt": [
        "diff-intelligence",
        "rules-validation",
        "port-map-resolver",
        "idempotency-guard",
        "conflict-resolver",
        "sync-readiness-gate",
        "rules-refinement",
    ],
    "adapt": [
        "python-empalme",
        "anti-regression-guard",
        "dependency-guard",
        "backend-contract-check",
        "release-guard",
    ],
    "backend-sync": [
        "backend-sync-orchestrator",
    ],
    "gates": ["quality-gate", "visual-regression"],
    "post-adapt": ["premerge-review", "backend-analysis", "report-generator"],
}

AGENT_SCRIPTS: dict[str, str] = {
    "diff-intelligence": "scripts/agents/run-diff-intelligence-agent.py",
    "rules-validation": "scripts/agents/run-rules-validation-agent.py",
    "port-map-resolver": "scripts/agents/run-port-map-resolver-agent.py",
    "idempotency-guard": "scripts/agents/run-idempotency-guard-agent.py",
    "conflict-resolver": "scripts/agents/run-conflict-resolver-agent.py",
    "sync-readiness-gate": "scripts/agents/run-sync-readiness-gate-agent.py",
    "rules-refinement": "scripts/agents/run-rules-refinement-agent.py",
    "python-empalme": "scripts/lovable-sync/empalme-orchestrator.py",
    "empalme": "scripts/lovable-sync/empalme-orchestrator.py",
    "anti-regression-guard": "scripts/agents/run-anti-regression-guard-agent.py",
    "dependency-guard": "scripts/agents/run-dependency-guard-agent.py",
    "backend-contract-check": "scripts/agents/run-backend-contract-check-agent.py",
    "release-guard": "scripts/agents/run-release-guard-agent.py",
    "quality-gate": "scripts/agents/run-quality-gate-agent.py",
    "visual-regression": "scripts/agents/run-visual-regression-agent.py",
    "premerge-review": "scripts/agents/run-premerge-review-agent.py",
    "backend-analysis": "scripts/agents/run-backend-analysis-agent.py",
    "report-generator": "scripts/agents/run-report-generator-agent.py",
    "backend-sync-orchestrator": "scripts/agents/run-backend-sync-orchestrator.py",
}

BLOCKING_AGENTS = {
    "diff-intelligence", "rules-validation", "port-map-resolver",
    "idempotency-guard", "conflict-resolver", "sync-readiness-gate",
    "python-empalme", "empalme", "anti-regression-guard", "dependency-guard", "backend-contract-check",
    "release-guard", "quality-gate",
}


def load_agents_config(cfg: dict[str, Any]) -> dict[str, Any]:
    path = CICD_ROOT / "dsf" / "agents.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"chain": []}


def change_manifest_path(args: argparse.Namespace) -> Path:
    env = os.environ.get("DSF_CHANGE_MANIFEST")
    if env:
        return Path(env)
    for c in (Path(args.cicd_dir) / "lovable-change-manifest.json", Path(args.lovable_dir) / "lovable-change-manifest.json"):
        if c.is_file():
            return c
    return Path(args.cicd_dir) / "lovable-change-manifest.json"


def diff_intelligence_path(run_id: str) -> Path:
    return artifacts_dir(run_id) / f"dsf-diff-intelligence-{run_id}.json"


def run_agent(agent_id: str, args: argparse.Namespace) -> dict[str, Any]:
    script_rel = AGENT_SCRIPTS.get(agent_id)
    if not script_rel:
        return {"agent": agent_id, "ok": False, "error": "script desconocido"}
    script = CICD_ROOT / script_rel
    if not script.exists():
        return {"agent": agent_id, "ok": False, "error": f"no existe {script}"}

    manifest = change_manifest_path(args)
    cmd: list[str] = [sys.executable, str(script)]
    common_manifest = [
        "--lovable-dir", args.lovable_dir,
        "--change-manifest", str(manifest),
        "--run-id", args.run_id,
    ]

    if agent_id == "diff-intelligence":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--change-manifest", str(manifest), "--run-id", args.run_id])
    elif agent_id == "rules-validation":
        cmd.extend([args.lovable_dir, "--strict"])
    elif agent_id == "port-map-resolver":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--change-manifest", str(manifest), "--run-id", args.run_id])
        dp = diff_intelligence_path(args.run_id)
        if dp.is_file():
            cmd.extend(["--diff-intelligence", str(dp)])
    elif agent_id == "idempotency-guard":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--run-id", args.run_id])
    elif agent_id == "conflict-resolver":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--change-manifest", str(manifest), "--run-id", args.run_id])
    elif agent_id == "sync-readiness-gate":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--change-manifest", str(manifest), "--run-id", args.run_id])
    elif agent_id == "rules-refinement":
        cmd.append(args.lovable_dir)
    elif agent_id == "anti-regression-guard":
        cmd.extend([
            "--lovable-dir", args.lovable_dir,
            "--web-dir", args.web_dir,
            "--cicd-dir", args.cicd_dir,
            "--run-id", args.run_id,
            "--python-result", str(Path(args.cicd_dir) / f"empalme-python-result-{args.run_id}.json"),
        ])
    elif agent_id in ("dependency-guard", "backend-contract-check", "release-guard", "visual-regression"):
        cmd.extend(common_manifest)
    elif agent_id == "backend-sync-orchestrator":
        back_dir = os.environ.get("BACK_DIR", str(Path(args.cicd_dir).parent / "DoEventsBack"))
        cmd.extend([
            "--lovable-dir", args.lovable_dir,
            "--web-dir", args.web_dir,
            "--back-dir", back_dir,
            "--cicd-dir", args.cicd_dir,
            "--change-manifest", str(manifest),
            "--run-id", args.run_id,
        ])
        if is_dry_run():
            cmd.append("--dry-run")
        if os.environ.get("BSF_SKIP_DEPLOY") == "1":
            cmd.append("--skip-deploy")
    elif agent_id == "quality-gate":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--cicd-dir", args.cicd_dir, "--run-id", args.run_id])
        if is_dry_run():
            cmd.append("--skip-build")
    elif agent_id in ("premerge-review", "backend-analysis"):
        cmd.append(args.web_dir)
        if agent_id == "premerge-review" and args.design_comparison:
            cmd.append(args.design_comparison)
    elif agent_id == "report-generator":
        cmd.extend(["--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
                    "--cicd-dir", args.cicd_dir, "--run-id", args.run_id])
    elif agent_id in ("python-empalme", "empalme"):
        cmd.extend([
            "--lovable-dir", args.lovable_dir, "--web-dir", args.web_dir,
            "--cicd-dir", args.cicd_dir,
            "--port-map", str(Path(args.web_dir) / ".lovable-port-map.json"),
            "--run-id", args.run_id,
        ])
        if manifest.is_file():
            cmd.extend(["--change-manifest", str(manifest)])
        dp = diff_intelligence_path(args.run_id)
        if dp.is_file():
            cmd.extend(["--diff-intelligence", str(dp)])
        if is_dry_run():
            cmd.append("--dry-run")
        elif os.environ.get("CURSOR_API_KEY") or os.environ.get("DSF_CURSOR_FALLBACK") == "1":
            cmd.append("--cursor-fallback")

    proc = subprocess.run(cmd, env={**os.environ, "DSF_CHANGE_MANIFEST": str(manifest)},
                          capture_output=True, text=True, timeout=3600)
    return {
        "agent": agent_id,
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "elapsedSec": round(time.time(), 2),
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-1000:],
        "dryRun": is_dry_run(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF Orchestrator v1.1")
    parser.add_argument("--phase", default="all",
                        choices=["all", "pre-adapt", "adapt", "backend-sync", "gates", "post-adapt"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", f"local-{int(time.time())}"))
    parser.add_argument("--lovable-dir", default=os.environ.get("LOVABLE_DIR", ""))
    parser.add_argument("--web-dir", default=os.environ.get("WEB_DIR", ""))
    parser.add_argument("--cicd-dir", default=os.environ.get("CICD_DIR", str(CICD_ROOT)))
    parser.add_argument("--design-comparison", default=os.environ.get("DESIGN_COMPARISON", ""))
    parser.add_argument("--skip-adapt", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DSF_AGENT_DRY_RUN"] = "1"
        os.environ.setdefault("DSF_LOCAL_MODE", "1")

    cfg = load_config()
    if not args.lovable_dir:
        args.lovable_dir = str(CICD_ROOT.parent / "discover-joyful-feed")
    if not args.web_dir:
        args.web_dir = str(CICD_ROOT.parent / "DoEventsWEB")

    os.environ.update({
        "CICD_DIR": args.cicd_dir, "LOVABLE_DIR": args.lovable_dir,
        "WEB_DIR": args.web_dir, "GITHUB_RUN_ID": args.run_id,
        "DSF_LOCAL_RUN_ID": args.run_id,
    })

  fullstack = os.environ.get("DSF_AGENT_MODE", "frontend-only") == "fullstack"
    phases = ["pre-adapt", "adapt", "gates", "post-adapt"] if args.phase == "all" else [args.phase]
    if fullstack and args.phase == "all":
        phases = ["pre-adapt", "adapt", "backend-sync", "gates", "post-adapt"]
    if args.skip_adapt:
        phases = [p for p in phases if p not in ("adapt", "gates")]

    chain_cfg = load_agents_config(cfg)
    results: list[dict] = []
    rc = 0

    for phase in phases:
        print(f"\n=== DSF v1.1 — {phase} ===", flush=True)
        for agent_id in PHASE_AGENTS[phase]:
            meta = next((a for a in chain_cfg.get("chain", []) if a.get("id") == agent_id), {})
            print(f"  -> {agent_id}", flush=True)
            r = run_agent(agent_id, args)
            results.append(r)
            blocking = meta.get("blocking", agent_id in BLOCKING_AGENTS)
            if not r.get("ok") and blocking and not is_dry_run():
                rc = 1
                print(f"  BLOQUEADO: {agent_id}", file=sys.stderr)
                break
            print(f"  {'OK' if r.get('ok') else 'FAIL'}", flush=True)
        if rc:
            break

    summary = {
        "runId": args.run_id,
        "framework": "DSF v1.1",
        "phases": phases,
        "results": results,
        "ok": all(r.get("ok") for r in results),
    }
    write_report("orchestrator-summary.json", summary, args.run_id)
    gh_output("orchestrator_ok", str(summary["ok"]).lower())
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return rc if not summary["ok"] and not is_dry_run() else 0


if __name__ == "__main__":
    sys.exit(main())
