#!/usr/bin/env python3
"""Valida resultado del pipeline DSF Lovable → WEB → DEV (gates bloqueantes)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_TARGET_SIM = 98.0


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_dsf_config(cicd_dir: Path) -> dict:
    cfg_path = cicd_dir / "cicd.config.json"
    if not cfg_path.exists():
        return {}
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return cfg.get("dsf", {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-before", required=True)
    parser.add_argument("--design-after", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--lovable-sha", default="")
    parser.add_argument("--agent-ran", default="false")
    parser.add_argument("--deploy-ran", default="false")
    parser.add_argument("--smoke-ran", default="false")
    parser.add_argument("--smoke-ok", default="false")
    parser.add_argument("--port-map-ok", default="true")
    parser.add_argument("--min-similarity", type=float, default=0)
    parser.add_argument("--cicd-dir", default=".")
    parser.add_argument("--blocking", default="true")
    args = parser.parse_args()

    dsf = load_dsf_config(Path(args.cicd_dir))
    blocking = args.blocking.lower() == "true" and dsf.get("blockingGates", True)
    target_sim = float(dsf.get("targetSimilarityPercent", DEFAULT_TARGET_SIM))
    if args.min_similarity > 0:
        target_sim = args.min_similarity

    errors: list[str] = []
    warnings: list[str] = []

    before = load_json(Path(args.design_before))
    after = load_json(Path(args.design_after)) if args.design_after else before
    manifest = load_json(Path(args.manifest)) if args.manifest else {}

    if not before:
        errors.append("Falta design-comparison (baseline)")

    before_sim = float(before.get("overallSimilarityPercent", 0))
    after_sim = float(after.get("overallSimilarityPercent", before_sim))
    pending = int(after.get("summary", {}).get("needsAdaptation", 0)) + int(
        after.get("missingInWebCount", after.get("summary", {}).get("missingInWeb", 0))
    )

    agent_ran = args.agent_ran.lower() == "true"
    deploy_ran = args.deploy_ran.lower() == "true"
    smoke_ran = args.smoke_ran.lower() == "true"
    smoke_ok = args.smoke_ok.lower() == "true"
    port_map_ok = args.port_map_ok.lower() == "true"

    requires_agent = bool(
        manifest.get("requiresAgent")
        or before.get("requiresAgentForDesignAlignment")
        or manifest.get("hasUiChanges")
        or manifest.get("hasRulesChanges")
    )
    force_below = dsf.get("forceAgentBelowSimilarity", True)
    needs_agent = requires_agent or (force_below and before_sim < target_sim)

    if needs_agent and not agent_ran:
        errors.append("Se requería agente (cambios UI/reglas o similitud baja) pero adapt fue omitido")

    if not deploy_ran:
        errors.append("Deploy DEV no se ejecutó")

    if dsf.get("requirePortMapCoverage", True) and not port_map_ok:
        errors.append("Port-map incompleto: archivos Lovable sin destino WEB mapeado")

    if dsf.get("requireSmokeTests", True):
        if not smoke_ran:
            errors.append("Smoke tests DEV no se ejecutaron")
        elif not smoke_ok:
            errors.append("Smoke tests DEV fallaron")

    if after_sim < target_sim:
        msg = (
            f"Similitud {after_sim}% < objetivo {target_sim}% — "
            f"quedan ~{pending} gaps pendientes"
        )
        if blocking:
            errors.append(msg)
        else:
            warnings.append(msg)

    if before_sim > 0 and after_sim < before_sim - 5:
        warnings.append(f"Similitud empeoró: {before_sim}% → {after_sim}%")

    result = {
        "ok": len(errors) == 0,
        "framework": "DSF",
        "blockingGates": blocking,
        "errors": errors,
        "warnings": warnings,
        "lovableSha": args.lovable_sha,
        "similarityBefore": before_sim,
        "similarityAfter": after_sim,
        "similarityDelta": round(after_sim - before_sim, 2),
        "targetSimilarity": target_sim,
        "pendingGaps": pending,
        "agentRan": agent_ran,
        "deployRan": deploy_ran,
        "smokeRan": smoke_ran,
        "smokeOk": smoke_ok,
        "portMapOk": port_map_ok,
        "requiresGapEmpalme": after_sim < target_sim,
        "qaPromotionEnabled": dsf.get("qaPromotion", {}).get("enabled", False),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    for w in warnings:
        print(f"AVISO: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
