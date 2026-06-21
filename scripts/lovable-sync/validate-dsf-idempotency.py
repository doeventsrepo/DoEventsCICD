#!/usr/bin/env python3
"""Valida idempotencia DSF — entradas duplicadas en index, port-map y reglas."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dsf_idempotency import run_all


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    strict = "--strict" in sys.argv
    result = run_all(root)

    for e in result["errors"]:
        print(f"ERROR: {e}", file=sys.stderr)
    for w in result.get("warnings") or []:
        print(f"AVISO: {w}")

    print(json.dumps({"ok": result["passed"], "errors": result["errorCount"], "warnings": result["warningCount"]}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
