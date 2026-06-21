#!/usr/bin/env python3
"""Vigila y encadena ejecuciones de gap-empalme vía GitHub Actions hasta objetivo DSF.

Modos:
  poll   — Espera runs ya lanzados (por defecto si --run-id)
  launch — Dispara dsf-gap-batch-loop.yml (recomendado, un job encadena todos los batches)
  chain  — Dispara dsf-gap-empalme.yml repetidamente hasta objetivo o max-runs

Estado persistente: gap-watchdog-status.json en el directorio indicado.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip() or "gh failed")
    return r.stdout.strip()


def load_status(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"startedAt": utc_now(), "runs": [], "state": "idle"}


def save_status(path: Path, data: dict) -> None:
    data["updatedAt"] = utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def wait_run(repo: str, run_id: str, poll_sec: int = 45) -> dict:
    while True:
        out = gh(
            "run", "view", run_id, "--repo", repo,
            "--json", "status,conclusion,url,displayTitle",
        )
        data = json.loads(out)
        if data["status"] == "completed":
            return data
        print(f"[watchdog] run {run_id} en curso… ({data.get('displayTitle', '')})", flush=True)
        time.sleep(poll_sec)


def parse_summary_from_run(repo: str, run_id: str) -> dict | None:
    try:
        dl = Path(tempfile.mkdtemp(prefix=f"gap-wd-{run_id}-"))
        gh("run", "download", run_id, "--repo", repo, "-D", str(dl))
        for pattern in ("gap-loop-summary-*.json", "gap-empalme-summary-*.json"):
            for p in dl.rglob(pattern):
                return json.loads(p.read_text(encoding="utf-8"))
        for p in dl.rglob("design-comparison-after.json"):
            c = json.loads(p.read_text(encoding="utf-8"))
            pending = int(c.get("summary", {}).get("needsAdaptation", 0)) + int(
                c.get("missingInWebCount", c.get("summary", {}).get("missingInWeb", 0))
            )
            return {
                "finalSimilarity": c.get("overallSimilarityPercent", 0),
                "finalPendingGaps": pending,
            }
    except (RuntimeError, OSError, json.JSONDecodeError) as e:
        print(f"AVISO: no se pudo leer resumen run {run_id}: {e}", file=sys.stderr)
    return None


def objective_met(summary: dict | None, target: float, require_zero: bool) -> bool:
    if not summary:
        return False
    sim = float(summary.get("finalSimilarity") or summary.get("afterSimilarity") or 0)
    pending = int(
        summary.get("finalPendingGaps")
        or summary.get("gapsRemaining")
        or summary.get("pendingGaps")
        or 999
    )
    if require_zero:
        return sim >= target and pending == 0
    return sim >= target


def launch_batch_loop(repo: str, args: argparse.Namespace) -> str:
    gh(
        "workflow", "run", "dsf-gap-batch-loop.yml", "--repo", repo,
        "-f", f"lovable_ref={args.lovable_ref}",
        "-f", f"web_cicd_branch={args.web_branch}",
        "-f", f"target_similarity={args.target}",
        "-f", f"max_batches={args.max_batches}",
        "-f", f"batch_size={args.batch_size}",
        "-f", f"deploy_dev_after={'true' if args.deploy else 'false'}",
        "-f", f"require_zero_gaps={'true' if args.require_zero_gaps else 'false'}",
    )
    time.sleep(8)
    out = gh("run", "list", "--repo", repo, "--workflow=dsf-gap-batch-loop.yml", "--limit", "1", "--json", "databaseId")
    return str(json.loads(out)[0]["databaseId"])


def launch_gap_empalme(repo: str, args: argparse.Namespace) -> str:
    gh(
        "workflow", "run", "dsf-gap-empalme.yml", "--repo", repo,
        "-f", f"lovable_ref={args.lovable_ref}",
        "-f", f"web_cicd_branch={args.web_branch}",
        "-f", "batch_index=1",
        "-f", f"batch_size={args.batch_size}",
        "-f", "run_agent=true",
        "-f", f"deploy_dev_after={'true' if args.deploy else 'false'}",
    )
    time.sleep(8)
    out = gh("run", "list", "--repo", repo, "--workflow=dsf-gap-empalme.yml", "--limit", "1", "--json", "databaseId")
    return str(json.loads(out)[0]["databaseId"])


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF gap batch watchdog (GitHub Actions)")
    parser.add_argument("--repo", default="doeventsrepo/DoEventsCICD")
    parser.add_argument("--mode", choices=["launch", "chain", "poll"], default="launch")
    parser.add_argument("--run-id", help="Solo poll: ID de run a vigilar")
    parser.add_argument("--lovable-ref", default="main")
    parser.add_argument("--web-branch", default="feature/cicd/dev-automation")
    parser.add_argument("--target", type=float, default=98.0)
    parser.add_argument("--max-batches", type=int, default=25)
    parser.add_argument("--max-runs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--deploy", action="store_true", default=True)
    parser.add_argument("--no-deploy", action="store_true")
    parser.add_argument("--require-zero-gaps", action="store_true", default=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--poll-sec", type=int, default=45)
    parser.add_argument("--then-launch", action="store_true", help="Tras poll: lanzar batch-loop si no se cumplió objetivo")
    args = parser.parse_args()
    if args.no_deploy:
        args.deploy = False
    if args.allow_partial:
        args.require_zero_gaps = False

    status_path = Path(args.status_file)
    status = load_status(status_path)
    status["state"] = "running"
    status["config"] = {"target": args.target, "requireZeroGaps": args.require_zero_gaps, "mode": args.mode}
    save_status(status_path, status)

    try:
        if args.mode == "poll":
            if not args.run_id:
                print("ERROR: --run-id requerido en modo poll", file=sys.stderr)
                return 1
            run_ids = [args.run_id]
        elif args.mode == "launch":
            rid = launch_batch_loop(args.repo, args)
            print(f"[watchdog] lanzado dsf-gap-batch-loop run {rid}", flush=True)
            run_ids = [rid]
        else:
            for i in range(args.max_runs):
                rid = launch_gap_empalme(args.repo, args)
                print(f"[watchdog] chain {i + 1}/{args.max_runs} run {rid}", flush=True)
                result = wait_run(args.repo, rid, args.poll_sec)
                summary = parse_summary_from_run(args.repo, rid)
                status["runs"].append({"id": rid, "conclusion": result.get("conclusion"), "summary": summary})
                save_status(status_path, status)
                if objective_met(summary, args.target, args.require_zero_gaps):
                    status["state"] = "completed"
                    save_status(status_path, status)
                    print(json.dumps({"ok": True, "runId": rid, "summary": summary}, indent=2))
                    return 0
            status["state"] = "incomplete"
            save_status(status_path, status)
            return 1

        for rid in run_ids:
            result = wait_run(args.repo, rid, args.poll_sec)
            summary = parse_summary_from_run(args.repo, rid)
            status["runs"].append({"id": rid, "conclusion": result.get("conclusion"), "summary": summary})
            save_status(status_path, status)
            ok = objective_met(summary, args.target, args.require_zero_gaps)
            print(json.dumps({"ok": ok, "runId": rid, "url": result.get("url"), "summary": summary}, indent=2))
            if ok:
                status["state"] = "completed"
                save_status(status_path, status)
                return 0
            if args.then_launch and args.mode == "poll":
                rid2 = launch_batch_loop(args.repo, args)
                print(f"[watchdog] objetivo no cumplido — batch-loop {rid2}", flush=True)
                result2 = wait_run(args.repo, rid2, args.poll_sec)
                summary2 = parse_summary_from_run(args.repo, rid2)
                status["runs"].append({"id": rid2, "conclusion": result2.get("conclusion"), "summary": summary2})
                save_status(status_path, status)
                if objective_met(summary2, args.target, args.require_zero_gaps):
                    status["state"] = "completed"
                    save_status(status_path, status)
                    return 0

        status["state"] = "incomplete"
        save_status(status_path, status)
        return 1
    except KeyboardInterrupt:
        status["state"] = "interrupted"
        save_status(status_path, status)
        return 130
    except RuntimeError as e:
        status["state"] = "error"
        status["error"] = str(e)
        save_status(status_path, status)
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
