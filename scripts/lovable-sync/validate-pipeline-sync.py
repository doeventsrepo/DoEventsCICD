#!/usr/bin/env python3
"""Valida resultado del pipeline Lovable → WEB → DEV."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TARGET_SIM = 98.0


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-before", required=True)
    parser.add_argument("--design-after", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--lovable-sha", default="")
    parser.add_argument("--agent-ran", default="false")
    parser.add_argument("--deploy-ran", default="false")
    parser.add_argument("--min-similarity", type=float, default=0)
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    before = load_json(Path(args.design_before))
    after = load_json(Path(args.design_after)) if args.design_after else before
    manifest = load_json(Path(args.manifest)) if args.manifest else {}

    if not before:
        errors.append("Falta design-comparison (baseline)")
    if not args.lovable_sha:
        warnings.append("Sin lovable_sha registrado")

    before_sim = float(before.get("overallSimilarityPercent", 0))
    after_sim = float(after.get("overallSimilarityPercent", before_sim))
    pending = int(after.get("summary", {}).get("needsAdaptation", 0)) + int(
        after.get("missingInWebCount", after.get("summary", {}).get("missingInWeb", 0))
    )

    agent_ran = args.agent_ran.lower() == "true"
    deploy_ran = args.deploy_ran.lower() == "true"
    requires_agent = bool(manifest.get("requiresAgent") or before.get("requiresAgentForDesignAlignment"))

    if requires_agent and not agent_ran:
        errors.append("Se requería agente (gaps de diseño) pero adapt fue omitido")

    if args.deploy_ran.lower() not in ("true", "false"):
        warnings.append(f"deploy_ran ambiguo: {args.deploy_ran}")

    if not deploy_ran:
        errors.append("Deploy DEV no se ejecutó (deploy_dev_after debe ser true)")

    if args.min_similarity > 0 and after_sim < args.min_similarity:
        warnings.append(
            f"Similitud post-sync {after_sim}% < umbral {args.min_similarity}% — "
            f"ejecutar lovable-gap-empalme"
        )

    if after_sim < TARGET_SIM:
        warnings.append(
            f"Similitud {after_sim}% < objetivo {TARGET_SIM}% — quedan ~{pending} gaps; "
            "considerar lovable-gap-empalme"
        )

    result = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "lovableSha": args.lovable_sha,
        "similarityBefore": before_sim,
        "similarityAfter": after_sim,
        "similarityDelta": round(after_sim - before_sim, 2),
        "pendingGaps": pending,
        "agentRan": agent_ran,
        "deployRan": deploy_ran,
        "requiresGapEmpalme": after_sim < TARGET_SIM,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))

    for w in warnings:
        print(f"AVISO: {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
