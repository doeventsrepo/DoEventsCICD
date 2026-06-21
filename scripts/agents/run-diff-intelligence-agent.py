#!/usr/bin/env python3
"""Agente 0 — diff-intelligence: analiza diff Lovable y genera change-manifest inicial."""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import (  # noqa: E402
    aggregate_risk,
    changed_ui_paths,
    compute_file_risk,
    load_manifest,
    norm_path,
    resolve_web_path,
    save_json,
)
from agent_base import artifacts_dir, gh_output, write_report  # noqa: E402

try:
    from empalme_rules import build_change_manifest_enriched, resolve_agent_tier
except ImportError:
    from empalme_rules import build_change_manifest_enriched, resolve_agent_tier  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF diff-intelligence")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    ui_paths = changed_ui_paths(manifest)

    files_analysis: list[dict] = []
    layers_union: set[str] = set()
    risks: list[str] = []

    enriched = build_change_manifest_enriched(lovable, ui_paths) if ui_paths else []
    enriched_map = {e["lovablePath"]: e for e in enriched}

    for rel in ui_paths:
        tier_info = enriched_map.get(rel) or resolve_agent_tier(rel, lovable)
        web_path, status, meta = resolve_web_path(rel, lovable_root=lovable, web_root=web)
        layers = tier_info.get("layers") or []
        layers_union.update(layers)
        risk = compute_file_risk(
            layers=layers,
            agent_tier=tier_info.get("agentTier", "python"),
            web_status=status,
            has_rule_id=bool(meta.get("ruleId")),
            backend_required=tier_info.get("backendRequired", False),
        )
        risks.append(risk)
        files_analysis.append({
            "lovablePath": rel,
            "webPath": web_path,
            "ruleId": meta.get("ruleId", ""),
            "domain": meta.get("domain", ""),
            "agentTier": tier_info.get("agentTier", "python"),
            "complexity": tier_info.get("complexity", "simple"),
            "layers": layers,
            "riskLevel": risk,
            "portMapStatus": status,
            "requiresManualReview": risk in ("high", "blocked"),
            "requiresBackend": tier_info.get("backendRequired", False),
        })

    overall_risk = aggregate_risk(risks) if risks else "low"
    change_id = f"dsf-{args.run_id}-{uuid.uuid4().hex[:8]}"

    initial = {
        "changeId": change_id,
        "createdAt": utc_now(),
        "source": "lovable",
        "target": "DoEventsWEB",
        "summary": manifest.get("summary") or f"DSF sync {args.run_id}",
        "filesChanged": {
            "src": ui_paths,
            "rules": [f.get("path") for f in manifest.get("changedFiles", []) if f.get("kind") == "rules"],
            "design": [f.get("path") for f in manifest.get("changedFiles", []) if f.get("kind") == "design-rules"],
            "quality": [f.get("path") for f in manifest.get("changedFiles", []) if f.get("kind") == "quality-rules"],
            "backendContracts": [],
        },
        "filesAnalysis": files_analysis,
        "layersChanged": sorted(layers_union),
        "agentPlan": {
            "diffIntelligence": True,
            "pythonEmpalme": overall_risk != "blocked",
            "cursorEscalation": False,
            "backendAnalysis": any(f.get("requiresBackend") for f in files_analysis),
            "manualReview": overall_risk in ("high", "blocked"),
        },
        "risk": {"level": overall_risk, "reasons": []},
        "backend": {
            "required": any(f.get("requiresBackend") for f in files_analysis),
            "endpoints": [],
        },
        "dependencies": {"packageJsonChanged": False, "newDependencies": []},
        "validation": {
            "lint": "pending", "typecheck": "pending", "build": "pending",
            "smoke": "pending", "visualRegression": "pending",
        },
        "rollback": {"strategy": "git-revert", "safeToRollback": overall_risk != "blocked", "affectedAreas": sorted(layers_union)},
        "decision": {"status": "blocked" if overall_risk == "blocked" else "pending", "notes": ""},
    }

    if overall_risk == "blocked":
        for f in files_analysis:
            if not f.get("webPath"):
                initial["risk"]["reasons"].append(f"webPath no resuelto: {f['lovablePath']}")
            if not f.get("ruleId"):
                initial["risk"]["reasons"].append(f"sin ruleId: {f['lovablePath']}")

    out = Path(args.out) if args.out else artifacts_dir(args.run_id) / f"dsf-diff-intelligence-{args.run_id}.json"
    save_json(out, initial)
    write_report(f"diff-intelligence-{args.run_id}.json", initial, args.run_id)

    gh_output("dsf_risk_level", overall_risk)
    gh_output("dsf_blocked", str(overall_risk == "blocked").lower())
    print(json.dumps({"ok": True, "riskLevel": overall_risk, "files": len(files_analysis)}, indent=2))
    return 1 if overall_risk == "blocked" else 0


if __name__ == "__main__":
    sys.exit(main())
