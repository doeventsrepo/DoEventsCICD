#!/usr/bin/env python3
"""Empalme Python-only para un batch de gaps (sin Cursor API)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD_ROOT / "scripts" / "lovable-sync"))

from empalme_engine import resolve_targets, run_empalme  # noqa: E402


def git_rev(repo: Path, ref: str = "HEAD") -> str | None:
    if not (repo / ".git").is_dir():
        return None
    try:
        return subprocess.check_output(
            ["git", "rev-parse", ref],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Empalme Python para gaps de un manifiesto")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--gap-manifest", required=True)
    parser.add_argument("--comparison", default="", help="design-comparison.json (opcional)")
    parser.add_argument("--run-id", default="gap-batch-local")
    parser.add_argument("--out", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    port_map = Path(args.port_map).resolve()
    manifest_path = Path(args.gap_manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gap_paths = [g.get("lovablePath", "") for g in manifest.get("gaps") or [] if g.get("lovablePath")]

    if not gap_paths:
        print(json.dumps({"ok": True, "skipped": True, "reason": "empty_batch"}, indent=2))
        return 0

    comparison_files = []
    if args.comparison and Path(args.comparison).is_file():
        comparison_files = json.loads(Path(args.comparison).read_text(encoding="utf-8")).get("files") or []

    strategy_path = CICD_ROOT / "cicd.config.json"
    python_max_sim = 85.0
    if strategy_path.is_file():
        cfg = json.loads(strategy_path.read_text(encoding="utf-8"))
        python_max_sim = float(cfg.get("dsf", {}).get("empalmeStrategy", {}).get("pythonMaxSimApply", 85))

    targets = resolve_targets(
        lovable_root=lovable,
        web_root=web,
        port_map_path=port_map,
        comparison_files=comparison_files,
        changed_paths=gap_paths,
        scope="diff-only",
        python_max_sim=python_max_sim,
        max_items=len(gap_paths) + 5,
    )

    from empalme_delta import load_anti_regression_config

    lovable_after = git_rev(lovable) or manifest.get("lovableSha", "")
    lovable_before = git_rev(lovable, "__last_sync__") or git_rev(lovable, "HEAD~1") or lovable_after

    empalme = run_empalme(
        lovable_root=lovable,
        web_root=web,
        port_map_path=port_map,
        targets=targets,
        dry_run=args.dry_run,
        lovable_before_rev=lovable_before,
        lovable_after_rev=lovable_after,
        anti_regression=load_anti_regression_config(CICD_ROOT),
    )

    payload = {
        "runId": args.run_id,
        "mode": "python-only",
        "gapPaths": gap_paths,
        "targetCount": len(targets),
        "appliedCount": len(empalme.applied),
        "skippedCount": len(empalme.skipped),
        "cursorRequiredCount": len(empalme.cursor_required),
        "manualRequiredCount": len(empalme.manual_required),
        "backendRequiredCount": len(empalme.backend_required),
        "applied": empalme.applied,
        "skipped": empalme.skipped[:20],
        "cursorRequired": empalme.cursor_required,
        "manualRequired": empalme.manual_required,
        "backendRequired": empalme.backend_required,
    }

    out = Path(args.out) if args.out else CICD_ROOT / "artifacts" / f"gap-batch-empalme-{args.run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if empalme.cursor_required and not args.dry_run:
        print("AVISO: algunos gaps requieren Cursor/manual — ver cursorRequired en JSON", file=sys.stderr)
    return 0 if empalme.applied or not gap_paths else 1


if __name__ == "__main__":
    sys.exit(main())
