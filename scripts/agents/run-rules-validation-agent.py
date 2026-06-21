#!/usr/bin/env python3
"""Agente 1 — rules-validation DSF v1.0 (estructura + reglas, --strict bloqueante)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
CICD_ROOT = AGENTS_DIR.parents[1]
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))

from agent_base import artifacts_dir, gh_output, write_report


def main() -> int:
    argv = sys.argv[1:]
    strict = "--strict" in argv
    lovable_dir = Path(next((a for a in argv if not a.startswith("-")), os.environ.get("LOVABLE_DIR", ".")))

    scripts = CICD_ROOT / "scripts" / "lovable-sync"
    checks = [
        ([sys.executable, str(scripts / "validate-dsf-structure.py"), str(lovable_dir)] + (["--strict"] if strict else []), "dsf_structure"),
        ([sys.executable, str(scripts / "validate-rules.py"), str(lovable_dir / "reglasActuacion")], "reglas_actuacion"),
        ([sys.executable, str(scripts / "validate-design-rules.py"), str(lovable_dir / "reglasDiseno")], "reglas_diseno"),
        ([sys.executable, str(scripts / "validate-empalme-rules.py"), str(lovable_dir)] + (["--strict"] if strict else []), "reglas_empalme"),
        ([sys.executable, str(scripts / "validate-dsf-idempotency.py"), str(lovable_dir), "--strict"], "idempotency"),
        ([sys.executable, str(scripts / "validate-calidad-rules.py"), str(lovable_dir)], "reglas_calidad"),
    ]

    results: dict[str, dict] = {}
    failed = False
    for cmd, name in checks:
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        results[name] = {"ok": ok, "exitCode": proc.returncode, "tail": (proc.stdout or proc.stderr)[-500:]}
        if not ok:
            failed = True

    combined = {"ok": not failed, "strict": strict, "checks": results}
    write_report("rules-validation-report.json", combined)
    gh_output("rules_validation_ok", str(not failed).lower())
    print(json.dumps({"ok": not failed, "strict": strict}, indent=2))
    return 1 if failed and strict else 0


if __name__ == "__main__":
    sys.exit(main())
