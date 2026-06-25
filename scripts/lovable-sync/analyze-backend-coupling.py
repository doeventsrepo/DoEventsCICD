#!/usr/bin/env python3
"""BSF — Calcula porcentaje de acoplamiento Frontend ↔ Backend."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import load_manifest, save_json
from agent_base import artifacts_dir, cicd_root, gh_output, write_report


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def load_registry() -> dict[str, Any]:
    p = cicd_root() / "dsf" / "backend-registry.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF analyze backend coupling")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--delta-json", default="")
    parser.add_argument("--contracts-json", default="")
    args = parser.parse_args()

    run_id = args.run_id
    delta_path = Path(args.delta_json) if args.delta_json else artifacts_dir(run_id) / f"backend-delta-{run_id}.json"
    contract_path = Path(args.contracts_json) if args.contracts_json else artifacts_dir(run_id) / f"backend-contract-check-{run_id}.json"

    delta = load_json(delta_path)
    contracts = load_json(contract_path)
    registry = load_registry()
    domains_total = len(registry.get("domains") or {})

    items = delta.get("items") or []
    requires = [i for i in items if i.get("requiresBackend")]
    implemented_findings = [
        f for f in (contracts.get("findings") or [])
        if f.get("implementedInDoEventsBack")
    ]
    pending_findings = [
        f for f in (contracts.get("findings") or [])
        if not f.get("implementedInDoEventsBack")
    ]

    fields_detected = sum(len(i.get("newFields") or []) for i in requires)
    fields_wired = 0  # actualizado por implement-agent post-run

    impl_report = load_json(artifacts_dir(run_id) / f"backend-implement-{run_id}.json")
    for applied in impl_report.get("applied") or []:
        fields_wired += len(applied.get("fields") or [])

    if fields_detected:
        field_coupling = min(100.0, round(100.0 * fields_wired / fields_detected, 2))
    else:
        field_coupling = 100.0 if not requires else 85.0

    contract_total = len(contracts.get("findings") or [])
    if contract_total:
        contract_coupling = round(100.0 * len(implemented_findings) / contract_total, 2)
    else:
        contract_coupling = 100.0 if not requires else 70.0

    domain_coverage = round(100.0 * len(delta.get("domainsAffected") or []) / max(domains_total, 1), 2)
    overall = round((field_coupling * 0.4 + contract_coupling * 0.4 + domain_coverage * 0.2), 2)

    result = {
        "runId": run_id,
        "overallCouplingPercent": overall,
        "fieldCouplingPercent": field_coupling,
        "contractCouplingPercent": contract_coupling,
        "domainCoveragePercent": domain_coverage,
        "requiresBackendCount": delta.get("requiresBackendCount", 0),
        "implementedContracts": len(implemented_findings),
        "pendingContracts": len(pending_findings),
        "domainsAffected": delta.get("domainsAffected") or [],
        "lambdaDirsToDeploy": delta.get("lambdaDirsToDeploy") or [],
    }

    out = artifacts_dir(run_id) / f"backend-coupling-{run_id}.json"
    save_json(out, result)
    write_report(f"backend-coupling-{run_id}.json", result, run_id)
    gh_output("backend_coupling_percent", str(overall))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
