#!/usr/bin/env python3
"""Agente 6 — backend-contract-check: valida contratos contra DoEventsBack."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import BACKEND_HINTS, load_backend_endpoints, load_manifest, load_yaml, norm_path, save_json
from agent_base import artifacts_dir, gh_output, write_report

ENDPOINT_RE = re.compile(r'''['"](/api/[^'"]+)['"]|['"](https?://[^'"]+/api/[^'"]+)['"]''')


def extract_endpoints(text: str) -> list[str]:
    found: set[str] = set()
    for m in ENDPOINT_RE.finditer(text):
        ep = m.group(1) or m.group(2)
        if ep:
            found.add(ep.split("?")[0])
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF backend-contract-check")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    policy = load_yaml(lovable / "reglasCalidad" / "backend-contract-policy.yml")
    contracts = load_backend_endpoints(lovable)
    contract_paths = {c.get("path", "") for c in contracts if c.get("path")}

    ui_paths = [
        norm_path(f.get("path", ""))
        for f in manifest.get("changedFiles", [])
        if f.get("kind") == "ui"
    ]

    findings: list[dict] = []
    blocked = False

    for rel in ui_paths:
        path = lovable / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not BACKEND_HINTS.search(text):
            continue
        endpoints = extract_endpoints(text)
        for ep in endpoints:
            implemented = ep in contract_paths or any(c.get("path") == ep and c.get("implementedInDoEventsBack") for c in contracts)
            item = {
                "lovablePath": rel,
                "endpoint": ep,
                "implementedInDoEventsBack": implemented,
                "authRequired": next((c.get("authRequired") for c in contracts if c.get("path") == ep), None),
            }
            if not implemented:
                item["riskLevel"] = "blocked"
                item["agentTier"] = "backend"
                item["requiresBackend"] = True
                item["requiresManualReview"] = True
                blocked = True
            else:
                item["riskLevel"] = "high"
            findings.append(item)

    result = {
        "runId": args.run_id,
        "findingsCount": len(findings),
        "findings": findings,
        "riskLevel": "blocked" if blocked else ("high" if findings else "low"),
        "requiresBackend": blocked or bool(findings),
        "requiresManualReview": blocked,
        "policy": policy.get("backendContractPolicy", {}),
    }

    out = artifacts_dir(args.run_id) / f"backend-contract-check-{args.run_id}.json"
    save_json(out, result)
    write_report(f"backend-contract-check-{args.run_id}.json", result, args.run_id)
    gh_output("backend_contract_blocked", str(blocked).lower())
    print(json.dumps({"ok": not blocked, "findings": len(findings)}, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
