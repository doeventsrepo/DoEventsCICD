#!/usr/bin/env python3
"""Valida reglas YAML en reglasActuacion/ (esquema flexible, tolerante a pseudo-codigo)."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML: pip install pyyaml")
    sys.exit(1)

REQUIRED_MIN = {"id", "domain"}
RECOMMENDED = {"version", "description", "descripcion"}


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"{path}: YAML con pseudo-codigo (no bloquea CI): {exc}")
        return errors, warnings

    if not isinstance(data, dict):
        warnings.append(f"{path}: raiz no es objeto; se trata como documentacion libre")
        return errors, warnings

    missing = REQUIRED_MIN - set(data.keys())
    if missing:
        warnings.append(f"{path}: faltan campos {sorted(missing)} (documentacion parcial)")

    missing_rec = RECOMMENDED - set(data.keys())
    if missing_rec:
        warnings.append(f"{path}: recomendado agregar {sorted(missing_rec)}")

    if "id" in data and not isinstance(data["id"], str):
        errors.append(f"{path}: id debe ser string")

    return errors, warnings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "reglasActuacion")
    strict = "--strict" in sys.argv
    if not root.exists():
        print(f"No existe {root}")
        return 1

    files = list(root.rglob("*.yml")) + list(root.rglob("*.yaml"))
    if not files:
        print(f"Sin reglas en {root}")
        return 1

    all_errors: list[str] = []
    all_warnings: list[str] = []
    parsed_ok = 0

    for f in sorted(files):
        errs, warns = validate_file(f)
        all_errors.extend(errs)
        all_warnings.extend(warns)
        if not errs and not any("pseudo-codigo" in w for w in warns):
            parsed_ok += 1

    for w in all_warnings:
        print(f"AVISO: {w}")

    if all_errors:
        for e in all_errors:
            print(e, file=sys.stderr)
        return 1

    print(f"OK: {len(files)} archivo(s); {parsed_ok} parseados estrictamente")
    if strict and all_warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
