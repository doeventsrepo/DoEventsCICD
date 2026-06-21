#!/usr/bin/env python3
"""DSF — Ejecuta batches de gap-empalme hasta alcanzar similitud objetivo o max batches."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd, cwd=cwd)


def sync_web_from_remote(web: Path, branch: str) -> None:
    """Actualiza checkout local tras push del agente (comparación post-batch correcta)."""
    if not (web / ".git").is_dir():
        print(f"AVISO: {web} sin .git — omitir sync remoto")
        return
    pat = os.environ.get("DOEVENTS_WEB_PAT", "")
    if pat:
        run([
            "git", "remote", "set-url", "origin",
            f"https://x-access-token:{pat}@github.com/doeventsrepo/DoEventsWEB.git",
        ], cwd=web)
    run(["git", "fetch", "origin", branch, "--depth", "1"], cwd=web)
    run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=web)
    print(f"WEB sincronizado con origin/{branch}")


def similarity(path: Path) -> float:
    return float(json.loads(path.read_text(encoding="utf-8"))["overallSimilarityPercent"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--cicd-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--target", type=float, default=98.0)
    parser.add_argument("--max-batches", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--analyze-only", action="store_true", help="Solo comparar y generar manifiesto de gaps (sin agente)")
    args = parser.parse_args()

    if not args.skip_agent and (
        os.environ.get("DSF_BLOCK_GITHUB") == "1" or os.environ.get("DSF_LOCAL_MODE") == "1"
    ):
        print("ERROR: gap loop con agente bloqueado en modo local. Usa --skip-agent o local-gap-loop.py", file=sys.stderr)
        return 1

    lovable = Path(args.lovable_dir)
    web = Path(args.web_dir)
    cicd = Path(args.cicd_dir)
    compare_script = cicd / "scripts/lovable-sync/compare-design-similarity.py"
    gap_manifest_script = cicd / "scripts/lovable-sync/build-gap-manifest.py"
    gap_agent_script = cicd / "scripts/lovable-sync/run-gap-empalme-agent.py"

    before_path = cicd / f"design-comparison-loop-before-{args.run_id}.json"
    run([sys.executable, str(compare_script), str(lovable), str(web), args.port_map, str(before_path)])
    current_sim = similarity(before_path)
    print(f"Similitud inicial: {current_sim}% (objetivo {args.target}%)")

    if current_sim >= args.target:
        print("Objetivo ya alcanzado — sin gap loop")
        return 0

    if args.skip_agent or not os.environ.get("CURSOR_API_KEY"):
        if args.analyze_only or args.skip_agent:
            gap_manifest = cicd / f"gap-manifest-batch-1-{args.run_id}.json"
            run([
                sys.executable, str(gap_manifest_script),
                str(before_path), str(gap_manifest),
                "--batch-size", str(args.batch_size),
                "--batch-index", "1",
                "--run-id", f"{args.run_id}-b1",
            ])
            gaps = json.loads(gap_manifest.read_text(encoding="utf-8"))
            summary = {
                "ok": False,
                "mode": "analyze-only",
                "finalSimilarity": current_sim,
                "target": args.target,
                "pendingGaps": gaps.get("totalPendingGaps", 0),
                "gapsInBatch": gaps.get("gapsInBatch", 0),
            }
            summary_path = cicd / f"gap-loop-summary-{args.run_id}.json"
            summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
            return 0
        print("AVISO: sin CURSOR_API_KEY o --skip-agent — gap loop solo analiza", file=sys.stderr)
        return 1

    os.environ.setdefault("LOVABLE_DIR", str(lovable))
    os.environ.setdefault("WEB_DIR", str(web))
    os.environ.setdefault("CICD_DIR", str(cicd))

    batches_run = 0
    for batch_idx in range(1, args.max_batches + 1):
        if current_sim >= args.target:
            break

        gap_manifest = cicd / f"gap-manifest-batch-{batch_idx}-{args.run_id}.json"
        run([
            sys.executable, str(gap_manifest_script),
            str(before_path), str(gap_manifest),
            "--batch-size", str(args.batch_size),
            "--batch-index", "1",
            "--run-id", f"{args.run_id}-b{batch_idx}",
        ])

        gaps = json.loads(gap_manifest.read_text(encoding="utf-8"))
        pending = int(gaps.get("totalPendingGaps", 0))
        if gaps.get("gapsInBatch", 0) == 0:
            print(f"Batch {batch_idx}: sin gaps en batch — fin loop (pendientes {pending})")
            break

        os.environ["GAP_MANIFEST_PATH"] = str(gap_manifest)
        branch = os.environ.get("AGENT_BRANCH", "feature/cicd/dev-automation")
        os.environ.setdefault("AGENT_BRANCH", branch)
        run([sys.executable, str(gap_agent_script)])
        sync_web_from_remote(web, branch)

        after_path = cicd / f"design-comparison-loop-after-b{batch_idx}-{args.run_id}.json"
        run([sys.executable, str(compare_script), str(lovable), str(web), args.port_map, str(after_path)])
        current_sim = similarity(after_path)
        before_path = after_path
        batches_run = batch_idx
        pending = int(json.loads(gap_manifest.read_text(encoding="utf-8")).get("totalPendingGaps", pending))
        print(f"Batch {batch_idx} completado — similitud: {current_sim}% (pendientes ~{pending})")

    final_pending = 0
    try:
        comp = json.loads(before_path.read_text(encoding="utf-8"))
        final_pending = int(comp.get("summary", {}).get("needsAdaptation", 0)) + int(
            comp.get("missingInWebCount", comp.get("summary", {}).get("missingInWeb", 0))
        )
    except (OSError, json.JSONDecodeError, KeyError):
        pass

    summary = {
        "ok": current_sim >= args.target and final_pending == 0,
        "targetReached": current_sim >= args.target,
        "gapsClosed": final_pending == 0,
        "finalSimilarity": current_sim,
        "finalPendingGaps": final_pending,
        "target": args.target,
        "batchesRun": batches_run,
    }
    summary_path = cicd / f"gap-loop-summary-{args.run_id}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
