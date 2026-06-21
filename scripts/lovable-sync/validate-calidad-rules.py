#!/usr/bin/env python3
"""Valida reglasCalidad/ en discover-joyful-feed."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML")
    sys.exit(1)

    REQUIRED = [
    "reglasCalidad/required-checks.yml",
    "reglasCalidad/forbidden-patterns.yml",
    "reglasCalidad/risk-policy.yml",
    "reglasCalidad/rollback-policy.yml",
    "reglasCalidad/dependency-policy.yml",
    "reglasCalidad/backend-contract-policy.yml",
    "reglasCalidad/accessibility-policy.yml",
    "reglasCalidad/responsive-policy.yml",
    "reglasCalidad/idempotency-policy.yml",
    "reglasCalidad/conflict-policy.yml",
]


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    warnings: list[str] = []
    for rel in REQUIRED:
        p = root / rel
        if not p.is_file():
            warnings.append(f"Falta {rel}")
            continue
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not data.get("id"):
            warnings.append(f"{rel}: falta id")

    rp = root / "reglasCalidad" / "risk-policy.yml"
    if rp.is_file():
        data = yaml.safe_load(rp.read_text(encoding="utf-8"))
        cp = (data or {}).get("cursorPolicy") or {}
        if cp.get("maxRetries", 0) != 0:
            warnings.append("cursorPolicy.maxRetries debe ser 0 (sin loops)")

    for w in warnings:
        print(f"AVISO: {w}")
    print(f"OK: validate-calidad-rules ({len(warnings)} avisos)")
    return 1 if any("Falta" in w for w in warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
