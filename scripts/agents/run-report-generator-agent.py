#!/usr/bin/env python3
"""Agente 14 — report-generator + DSF Score."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
CICD_ROOT = AGENTS_DIR.parents[1]
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from agent_base import artifacts_dir, gh_output, write_report
from dsf_score import compute_dsf_score


def load_art(art_dir: Path, name: str) -> dict | None:
    p = art_dir / name
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    matches = list(art_dir.glob(name.replace("{run_id}", "*")))
    return json.loads(matches[-1].read_text(encoding="utf-8")) if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF report-generator v1.0")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    cicd = Path(args.cicd_dir).resolve()
    art = artifacts_dir(args.run_id)
    rid = args.run_id

    diff = load_art(art, f"dsf-diff-intelligence-{rid}.json")
    readiness = load_art(art, f"sync-readiness-gate-{rid}.json")
    idempotency = load_art(art, f"idempotency-guard-{rid}.json")
    conflicts = load_art(art, f"conflict-resolver-{rid}.json")
    qg = load_art(art, f"quality-gate-{rid}.json")
    empalme_path = cicd / f"empalme-summary-{rid}.json"
    py_path = cicd / f"empalme-python-result-{rid}.json"
    empalme = json.loads(empalme_path.read_text()) if empalme_path.is_file() else {}
    py_result = json.loads(py_path.read_text()) if py_path.is_file() else {}

    score = compute_dsf_score(
        diff_intel=diff, empalme_summary=empalme, python_result=py_result,
        readiness=readiness, quality_gate=qg,
        blocked_count=1 if (diff or {}).get("decision", {}).get("status") == "blocked" else 0,
    )

    risk = (diff or {}).get("risk", {}).get("level", "unknown")
    md = [
        "# DSF Report v1.0", "",
        f"**Run:** {rid} | **Fecha:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", "",
        "## Resumen", (diff or {}).get("summary", "Sync DSF"), "",
        "## DSF Score", f"- syncEffectiveness: **{score['syncEffectiveness']}%**",
        f"- pythonCoverage: **{score['pythonCoverage']}%**",
        f"- similarityDelta: **{score['similarityDelta']}%**",
        f"- deployRecommended: **{score['deployRecommended']}**", "",
        "## Riesgo", f"**{risk}**", "",
        "## AgentTier", f"Python aplicado: {empalme.get('pythonApplied', 0)} | Cursor: {empalme.get('cursorEscalationUsed', False)}", "",
        "## Validaciones", f"quality-gate: {(qg or {}).get('passed', 'N/A')}",
        f"sync-readiness: {(readiness or {}).get('passed', 'N/A')}",
        f"idempotency: {(idempotency or {}).get('passed', 'N/A')}",
        f"conflicts: {(conflicts or {}).get('decision', 'N/A')}", "",
        "## Decisión final", (conflicts or {}).get("decision") or (diff or {}).get("decision", {}).get("status", "pending"),
    ]

    reports = cicd / "Reports"
    reports.mkdir(parents=True, exist_ok=True)
    md_path = reports / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-dsf-report-{rid}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    summary = {"runId": rid, "riskLevel": risk, "dsfScore": score, "reportPath": str(md_path)}
    write_report(f"dsf-final-report-{rid}.json", summary, rid)
    gh_output("dsf_score", str(score["syncEffectiveness"]))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
