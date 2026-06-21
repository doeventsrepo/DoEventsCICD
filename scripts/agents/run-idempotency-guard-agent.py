#!/usr/bin/env python3
"""Agente 2.3 — idempotency-guard: sin duplicados en index, port-map, reglas."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_idempotency import run_all
from dsf_shared import save_json
from agent_base import artifacts_dir, gh_output, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF idempotency-guard")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--strict-empalme", action="store_true", help="Bloquear si falta empalme en reglas con source")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    result = run_all(lovable)

    out = artifacts_dir(args.run_id) / f"idempotency-guard-{args.run_id}.json"
    save_json(out, {**result, "runId": args.run_id})
    write_report(f"idempotency-guard-{args.run_id}.json", result, args.run_id)
    gh_output("idempotency_passed", str(result["passed"]).lower())

    for e in result["errors"]:
        print(f"ERROR: {e}", file=sys.stderr)
    for w in result.get("warnings") or []:
        print(f"AVISO: {w}")
    print(json.dumps({"ok": result["passed"], "errors": result["errorCount"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
