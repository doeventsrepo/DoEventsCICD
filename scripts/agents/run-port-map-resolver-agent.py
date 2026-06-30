#!/usr/bin/env python3
"""Agente 2 — port-map-resolver: lovablePath → webPath, duplicados, dominio."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import load_component_index, load_manifest, load_port_map_yml, norm_path, resolve_web_path, save_json
from agent_base import artifacts_dir, gh_output, write_report


def detect_duplicates(lovable_root: Path, paths: list[str]) -> list[dict]:
    """Detecta nombres sospechosos de duplicación."""
    dupes: list[dict] = []
    suspicious = ("V2", "New", "Final", "Copy", "Lovable", "Temp")
    by_stem: dict[str, list[str]] = {}
    for rel in paths:
        p = Path(rel)
        stem = p.stem
        # Agrupar por carpeta + stem (evita falso positivo index.css vs pages/Index.tsx)
        key = f"{p.parent.as_posix().lower()}::{stem.lower()}"
        by_stem.setdefault(key, []).append(rel)
        for suf in suspicious:
            if suf.lower() in stem.lower():
                dupes.append({"lovablePath": rel, "reason": f"suspicious_name:{suf}", "duplicateRisk": True})

    for stem, group in by_stem.items():
        if len(group) > 1:
            for rel in group:
                dupes.append({"lovablePath": rel, "reason": "same_stem_multiple_files", "duplicateRisk": True})
    return dupes


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF port-map-resolver")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--diff-intelligence", default="")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))

    if args.diff_intelligence and Path(args.diff_intelligence).is_file():
        diff_data = json.loads(Path(args.diff_intelligence).read_text(encoding="utf-8"))
        ui_paths = diff_data.get("filesChanged", {}).get("src") or []
    else:
        ui_paths = [
            norm_path(f.get("path", ""))
            for f in manifest.get("changedFiles", [])
            if f.get("kind") == "ui"
        ]

    port_map_yml = load_port_map_yml(lovable)
    component_index = load_component_index(lovable)
    resolved: list[dict] = []
    blocked = False

    for rel in ui_paths:
        web_path, status, meta = resolve_web_path(rel, lovable_root=lovable, web_root=web)
        entry = {
            "lovablePath": rel,
            "webPath": web_path,
            "ruleId": meta.get("ruleId", ""),
            "domain": meta.get("domain", ""),
            "status": status,
            "duplicateCheck": meta.get("duplicateCheck", "unknown"),
            "existingEquivalent": meta.get("existingEquivalent", ""),
            "inPortMapYml": rel in port_map_yml,
            "inComponentIndex": rel in component_index,
            "webFileExists": (web / web_path).is_file() if web_path else False,
        }
        if status == "blocked" or (not web_path and status != "delegated"):
            entry["riskLevel"] = "blocked"
            entry["requiresManualReview"] = True
            blocked = True
        else:
            entry["riskLevel"] = "low"
            entry["requiresManualReview"] = False
        resolved.append(entry)

    dupes = detect_duplicates(lovable, ui_paths)
    try:
        from dsf.reliability import gate, load_reliability

        rel = load_reliability(Path(__file__).resolve().parents[2])
        if dupes and gate(rel, "portMapDuplicateHeuristicBlocks", False):
            blocked = True
    except ImportError:
        pass

    result = {
        "runId": args.run_id,
        "resolvedCount": len(resolved),
        "blockedCount": sum(1 for r in resolved if r.get("riskLevel") == "blocked"),
        "duplicateWarnings": dupes,
        "entries": resolved,
        "riskLevel": "blocked" if blocked else ("medium" if dupes else "low"),
        "requiresManualReview": blocked or bool(dupes),
    }

    out = artifacts_dir(args.run_id) / f"port-map-resolver-{args.run_id}.json"
    save_json(out, result)
    write_report(f"port-map-resolver-{args.run_id}.json", result, args.run_id)
    gh_output("port_map_blocked", str(blocked).lower())
    print(json.dumps({"ok": not blocked, "resolved": len(resolved), "blocked": blocked}, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
