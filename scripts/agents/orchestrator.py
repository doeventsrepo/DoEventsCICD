#!/usr/bin/env python3
"""
Orquestador multi-agente DSF — ejecuta la cadena de agentes en orden.

Fases:
  pre-adapt  → rules-validation, rules-refinement (sin API)
  adapt      → empalme + gap-loop (requiere CURSOR_API_KEY en CI)
  post-adapt → premerge-review, backend-analysis

Uso local (dry-run):
  python scripts/agents/orchestrator.py --dry-run --phase all
  DSF_LOCAL_MODE=1 python scripts/agents/orchestrator.py --phase pre-adapt

CI:
  python scripts/agents/orchestrator.py --phase all --run-id $GITHUB_RUN_ID
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
    "pre-adapt": ["rules-validation", "rules-refinement"],
    "adapt": ["empalme", "gap-empalme"],
    "post-adapt": ["premerge-review", "backend-analysis"],
}

AGENT_SCRIPTS: dict[str, str] = {
    "rules-validation": "scripts/agents/run-rules-validation-agent.py",
    "rules-refinement": "scripts/agents/run-rules-refinement-agent.py",
    "empalme": "scripts/lovable-sync/run-port-agent-api.py",
    "gap-empalme": "scripts/lovable-sync/dsf-gap-loop.py",
    "premerge-review": "scripts/agents/run-premerge-review-agent.py",
    "backend-analysis": "scripts/agents/run-backend-analysis-agent.py",
}


def load_agents_config(cfg: dict[str, Any]) -> dict[str, Any]:
    path = CICD_ROOT / "dsf" / "agents.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    tpl = CICD_ROOT / "templates" / "reglasFramework" / "agents.template.json"
    if tpl.exists():
        return json.loads(tpl.read_text(encoding="utf-8"))
    return {"chain": []}


def run_agent(agent_id: str, args: argparse.Namespace, env: dict[str, str]) -> dict[str, Any]:
    script_rel = AGENT_SCRIPTS.get(agent_id)
    if not script_rel:
        return {"agent": agent_id, "ok": False, "error": "script desconocido"}

    script = CICD_ROOT / script_rel
    if not script.exists():
        return {"agent": agent_id, "ok": False, "error": f"no existe {script}"}

    cmd: list[str] = [sys.executable, str(script)]

    if agent_id == "rules-validation":
        cmd.append(args.lovable_dir)
    elif agent_id == "rules-refinement":
        cmd.append(args.lovable_dir)
    elif agent_id in ("premerge-review", "backend-analysis"):
        cmd.append(args.web_dir)
        if agent_id == "premerge-review" and args.design_comparison:
            cmd.append(args.design_comparison)
    elif agent_id == "gap-empalme":
        cmd.extend([
            "--lovable-dir", args.lovable_dir,
            "--web-dir", args.web_dir,
            "--cicd-dir", args.cicd_dir,
            "--port-map", str(Path(args.web_dir) / ".lovable-port-map.json"),
            "--target", str(args.target_similarity),
            "--max-batches", str(args.max_gap_batches),
            "--batch-size", str(args.gap_batch_size),
            "--run-id", args.run_id,
        ])
        if is_dry_run() or not os.environ.get("CURSOR_API_KEY"):
            cmd.extend(["--skip-agent", "--analyze-only"])

    start = time.time()
    merged_env = {**os.environ, **env}
    proc = subprocess.run(cmd, env=merged_env, capture_output=True, text=True, timeout=3600)
    elapsed = round(time.time() - start, 2)
    return {
        "agent": agent_id,
        "ok": proc.returncode == 0,
        "exitCode": proc.returncode,
        "elapsedSec": elapsed,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-1000:],
        "dryRun": is_dry_run(),
    }


def resolve_phases(phase_arg: str) -> list[str]:
    if phase_arg == "all":
        return ["pre-adapt", "adapt", "post-adapt"]
    if phase_arg in PHASE_AGENTS:
        return [phase_arg]
    raise ValueError(f"Fase desconocida: {phase_arg}")


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF Multi-Agent Orchestrator")
    parser.add_argument("--phase", default="all", choices=["all", "pre-adapt", "adapt", "post-adapt"])
    parser.add_argument("--dry-run", action="store_true", help="Sin Cursor API ni GitHub")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", f"local-{int(time.time())}"))
    parser.add_argument("--lovable-dir", default=os.environ.get("LOVABLE_DIR", ""))
    parser.add_argument("--web-dir", default=os.environ.get("WEB_DIR", ""))
    parser.add_argument("--cicd-dir", default=os.environ.get("CICD_DIR", str(CICD_ROOT)))
    parser.add_argument("--design-comparison", default=os.environ.get("DESIGN_COMPARISON", ""))
    parser.add_argument("--target-similarity", type=float, default=98)
    parser.add_argument("--max-gap-batches", type=int, default=5)
    parser.add_argument("--gap-batch-size", type=int, default=20)
    parser.add_argument("--skip-adapt", action="store_true", help="Omitir empalme/gap (solo pre/post)")
    args = parser.parse_args()

    if args.dry_run:
        os.environ["DSF_AGENT_DRY_RUN"] = "1"
        os.environ.setdefault("DSF_LOCAL_MODE", "1")

    cfg = load_config()
    core = cfg.get("dsfCore", {})
    if not args.lovable_dir:
        args.lovable_dir = os.environ.get("LOVABLE_DIR") or str(CICD_ROOT.parent / "discover-joyful-feed")
    if not args.web_dir:
        args.web_dir = os.environ.get("WEB_DIR") or str(CICD_ROOT.parent / "DoEventsWEB")

    os.environ["CICD_DIR"] = args.cicd_dir
    os.environ["LOVABLE_DIR"] = args.lovable_dir
    os.environ["WEB_DIR"] = args.web_dir
    os.environ["DSF_LOCAL_RUN_ID"] = args.run_id
    os.environ["GITHUB_RUN_ID"] = args.run_id

    phases = resolve_phases(args.phase)
    if args.skip_adapt:
        phases = [p for p in phases if p != "adapt"]

    results: list[dict] = []
    rc = 0
    env_extra = {"DSF_TARGET_SIM": str(args.target_similarity)}

    for phase in phases:
        print(f"\n=== Orquestador DSF — fase {phase} ===", flush=True)
        for agent_id in PHASE_AGENTS[phase]:
            chain_cfg = load_agents_config(cfg)
            agent_meta = next((a for a in chain_cfg.get("chain", []) if a.get("id") == agent_id), {})
            if agent_meta.get("requiresApi") and is_dry_run():
                print(f"  [{agent_id}] SKIP (dry-run, requiresApi)", flush=True)
                results.append({"agent": agent_id, "ok": True, "skipped": True, "reason": "dry-run"})
                continue
            if agent_id == "empalme" and is_dry_run():
                sim = CICD_ROOT / "simulation" / "scripts" / "simulate-agent-dry-run.py"
                if sim.exists():
                    proc = subprocess.run(
                        [sys.executable, str(sim)],
                        env={**os.environ, **env_extra},
                        capture_output=True,
                        text=True,
                    )
                    r = {"agent": "empalme-dry-run", "ok": proc.returncode == 0, "exitCode": proc.returncode}
                    results.append(r)
                    rc = max(rc, 0 if r["ok"] else 1)
                    continue

            print(f"  -> {agent_id}", flush=True)
            r = run_agent(agent_id, args, env_extra)
            results.append(r)
            if not r.get("ok") and not r.get("skipped"):
                blocking = agent_meta.get("blocking", agent_id in ("empalme",))
                if blocking and not is_dry_run():
                    rc = 1
                    print(f"  ERROR: agente bloqueante {agent_id} falló", file=sys.stderr)
                    break
            print(f"  {'OK' if r.get('ok') else 'FAIL'} ({r.get('elapsedSec', 0)}s)", flush=True)

    summary = {
        "runId": args.run_id,
        "phases": phases,
        "dryRun": is_dry_run(),
        "framework": core.get("framework", "DSF"),
        "deployEnvironment": cfg.get("phases", {}).get("activeDeployEnvironment", "dev"),
        "results": results,
        "ok": all(r.get("ok") or r.get("skipped") for r in results),
    }
    write_report("orchestrator-summary.json", summary, args.run_id)
    gh_output("orchestrator_ok", str(summary["ok"]).lower())
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return rc if not summary["ok"] and not is_dry_run() else 0


if __name__ == "__main__":
    sys.exit(main())
