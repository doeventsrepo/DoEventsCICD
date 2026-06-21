#!/usr/bin/env python3
"""
Agente Python de empalme — transformación determinista Lovable → DoEventsWEB.

Sin Cursor API. Clasifica lo que requiere Cursor, manual o backend.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from empalme_engine import resolve_targets, run_empalme


def gh_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def load_comparison(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("files") or []


def load_changed_paths(manifest_path: Path) -> list[str]:
    if not manifest_path.is_file():
        return []
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return [f["path"] for f in data.get("changedFiles", []) if f.get("kind") == "ui"]


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF — Agente Python empalme (sin API)")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--comparison", default="", help="design-comparison.json (before)")
    parser.add_argument("--change-manifest", default="", help="lovable-change-manifest.json")
    parser.add_argument("--scope", choices=["diff-only", "gaps"], default="diff-only")
    parser.add_argument("--python-max-sim", type=float, default=85.0)
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="empalme-python-result.json")
    parser.add_argument("--run-id", default="local")
    args = parser.parse_args()

    lovable_root = Path(args.lovable_dir).resolve()
    web_root = Path(args.web_dir).resolve()
    port_map = Path(args.port_map).resolve()
    comparison_files = load_comparison(Path(args.comparison)) if args.comparison else []
    changed = load_changed_paths(Path(args.change_manifest)) if args.change_manifest else []

    if args.scope == "diff-only" and not changed:
        print("Sin cambios UI en manifiesto — empalme Python omitido (scope=diff-only)")
        result_payload = {
            "runId": args.run_id,
            "scope": args.scope,
            "skippedRun": True,
            "reason": "no_ui_changes",
            "applied": [],
            "skipped": [],
            "cursorRequired": [],
            "manualRequired": [],
            "backendRequired": [],
        }
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        gh_output("python_applied", "0")
        gh_output("cursor_required", "0")
        print(json.dumps(result_payload, indent=2))
        return 0

    targets = resolve_targets(
        lovable_root=lovable_root,
        web_root=web_root,
        port_map_path=port_map,
        comparison_files=comparison_files,
        changed_paths=changed if args.scope == "diff-only" else None,
        scope=args.scope,
        python_max_sim=args.python_max_sim,
        max_items=args.max_items,
    )

    from empalme_rules import build_change_manifest_enriched

    enriched = build_change_manifest_enriched(lovable_root, changed) if changed else []
    enriched_map = {e["lovablePath"]: e for e in enriched}

    empalme = run_empalme(
        lovable_root=lovable_root,
        web_root=web_root,
        port_map_path=port_map,
        targets=targets,
        dry_run=args.dry_run,
    )

    payload = {
        "runId": args.run_id,
        "scope": args.scope,
        "dryRun": args.dry_run,
        "targetCount": len(targets),
        "appliedCount": len(empalme.applied),
        "skippedCount": len(empalme.skipped),
        "cursorRequiredCount": len(empalme.cursor_required),
        "manualRequiredCount": len(empalme.manual_required),
        "backendRequiredCount": len(empalme.backend_required),
        "layerManifest": enriched,
        "applied": [
            {**a, "layers": enriched_map.get(a.get("lovablePath", ""), {}).get("layers", [])}
            for a in empalme.applied
        ],
        "skipped": empalme.skipped,
        "cursorRequired": empalme.cursor_required,
        "manualRequired": empalme.manual_required,
        "backendRequired": empalme.backend_required,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    gh_output("python_applied", str(len(empalme.applied)))
    gh_output("cursor_required", str(len(empalme.cursor_required)))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
