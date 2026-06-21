"""Cálculo DSF Score — efectividad de sincronización por run."""
from __future__ import annotations

from typing import Any


def compute_dsf_score(
    *,
    diff_intel: dict | None,
    empalme_summary: dict | None,
    python_result: dict | None,
    readiness: dict | None,
    quality_gate: dict | None,
    blocked_count: int = 0,
) -> dict[str, Any]:
    empalme = empalme_summary or {}
    py = python_result or {}
    applied = int(empalme.get("pythonApplied") or py.get("appliedCount") or 0)
    cursor_used = bool(empalme.get("cursorEscalationUsed"))
    cursor_req = len(py.get("cursorRequired") or [])
    target = int(py.get("targetCount") or 0) or max(applied + cursor_req, 1)

    python_coverage = round(100 * applied / target, 1) if target else 100.0
    sim_before = float(empalme.get("similarityBefore") or 0)
    sim_after = float(empalme.get("similarityFinal") or sim_before)
    sim_delta = round(sim_after - sim_before, 2)

    sync_effectiveness = python_coverage
    if quality_gate and quality_gate.get("passed"):
        sync_effectiveness = min(100.0, sync_effectiveness + 5)
    if readiness and readiness.get("passed"):
        sync_effectiveness = min(100.0, sync_effectiveness + 2)

    return {
        "syncEffectiveness": round(sync_effectiveness, 1),
        "pythonCoverage": python_coverage,
        "cursorEscalations": 1 if cursor_used else 0,
        "blockedCorrectly": blocked_count,
        "falseBlocks": 0,
        "similarityDelta": sim_delta,
        "deployRecommended": (
            (quality_gate or {}).get("passed", False)
            and (readiness or {}).get("passed", True)
            and (diff_intel or {}).get("decision", {}).get("status") != "blocked"
        ),
    }
