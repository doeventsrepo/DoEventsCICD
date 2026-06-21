#!/usr/bin/env python3
"""Genera change-manifest DSF alineado con reglasEmpalme/change-manifest.schema.yml."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from empalme_rules import build_change_manifest_enriched
from quality_policy import compute_risk_level, load_quality_policy


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF change-manifest builder")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--python-result", required=True)
    parser.add_argument("--summary", default="")
    parser.add_argument("--run-id", default="local")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cursor-used", action="store_true")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    py = json.loads(Path(args.python_result).read_text(encoding="utf-8"))
    policy = load_quality_policy(lovable)

    files_changed: list[dict] = []
    layers_union: set[str] = set()

    for item in py.get("applied") or []:
        layers = item.get("layers") or []
        if isinstance(layers, str):
            layers = [layers]
        layers_union.update(layers)
        files_changed.append({
            "lovablePath": item.get("lovablePath", ""),
            "webPath": item.get("webPath", ""),
            "agentTier": "python",
            "layers": layers,
            "applied": True,
            "reason": item.get("reason", ""),
        })

    for bucket, tier in (
        ("cursorRequired", "cursor"),
        ("manualRequired", "manual"),
        ("backendRequired", "backend"),
        ("skipped", "skipped"),
    ):
        for item in py.get(bucket) or []:
            info = next(
                (x for x in (py.get("layerManifest") or []) if x.get("lovablePath") == item.get("lovablePath")),
                {},
            )
            layers = info.get("layers") or []
            layers_union.update(layers)
            files_changed.append({
                "lovablePath": item.get("lovablePath", ""),
                "webPath": item.get("webPath", ""),
                "agentTier": tier,
                "layers": layers,
                "applied": False,
                "reason": item.get("reason", ""),
            })

    blocked = any(not f.get("webPath") for f in files_changed if f.get("agentTier") != "skipped")
    backend_req = py.get("backendRequiredCount", 0) > 0
    risk = compute_risk_level(
        layers=sorted(layers_union),
        agent_tier="cursor" if args.cursor_used else "python",
        blocked=blocked,
        backend_required=backend_req,
    )

    agent_used = "none"
    if py.get("appliedCount", 0) > 0 and args.cursor_used:
        agent_used = "python+cursor"
    elif py.get("appliedCount", 0) > 0:
        agent_used = "python"
    elif args.cursor_used:
        agent_used = "cursor"

    manifest = {
        "changeId": f"dsf-{args.run_id}-{uuid.uuid4().hex[:8]}",
        "generatedAt": utc_now(),
        "runId": args.run_id,
        "summary": args.summary or f"DSF sync {args.run_id}",
        "filesChanged": files_changed,
        "layersChanged": sorted(layers_union),
        "agentUsed": agent_used,
        "pythonAppliedCount": py.get("appliedCount", 0),
        "cursorEscalatedCount": len(py.get("cursorRequired") or []) if args.cursor_used else 0,
        "requiresBackend": backend_req,
        "requiresManualReview": py.get("manualRequiredCount", 0) > 0 or risk == "high",
        "buildRequired": True,
        "smokeRequired": True,
        "riskLevel": risk,
        "rollback": {
            "strategy": "git-revert",
            "safeToRollback": risk != "blocked" and not backend_req,
            "backendImpact": backend_req,
            "affectedAreas": sorted(layers_union),
        },
        "layerManifest": py.get("layerManifest") or [],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "changeId": manifest["changeId"], "riskLevel": risk}, indent=2))
    return 0 if risk != "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
