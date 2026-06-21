#!/usr/bin/env python3
"""Valida reglasDiseno/ (tokens, breakpoints, convenciones)."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

REQUIRED_FILES = ("tokens.yml", "breakpoints.yml", "component-conventions.yml")
REQUIRED_FIELDS = {"id", "domain", "version", "description"}


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{path.name}: YAML inválido: {exc}")
        return errors, warnings
    if not isinstance(data, dict):
        errors.append(f"{path.name}: raíz debe ser objeto")
        return errors, warnings
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"{path.name}: faltan {sorted(missing)}")
    if data.get("domain") != "diseno":
        warnings.append(f"{path.name}: domain debería ser 'diseno'")
    return errors, warnings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "reglasDiseno")
    if not root.exists():
        print(f"AVISO: {root} no existe (opcional en apps legacy)")
        return 0

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for name in REQUIRED_FILES:
        p = root / name
        if not p.exists():
            all_errors.append(f"Falta archivo obligatorio: {name}")
            continue
        errs, warns = validate_file(p)
        all_errors.extend(errs)
        all_warnings.extend(warns)

    for w in all_warnings:
        print(f"AVISO: {w}")
    if all_errors:
        for e in all_errors:
            print(e, file=sys.stderr)
        return 1
    print(f"OK: reglasDiseno validadas ({len(REQUIRED_FILES)} archivos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
