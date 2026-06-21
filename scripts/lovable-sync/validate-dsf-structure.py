#!/usr/bin/env python3
"""Validación estructura DSF v1.0 — bloqueante con --strict."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

REQUIRED = [
    "reglasEmpalme/schema-capas.yml",
    "reglasEmpalme/routing-agentes.yml",
    "reglasEmpalme/component-index.yml",
    "reglasEmpalme/port-map.yml",
    "reglasEmpalme/change-manifest.schema.yml",
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
    "reglasRelease/feature-flags.yml",
    "reglasRelease/compatibility-policy.yml",
    "reglasObservabilidad/events-catalog.yml",
    "contratosBackend/endpoints.yml",
    "decision-log.md",
]


def check_yaml_id(path: Path) -> list[str]:
    errs: list[str] = []
    if not path.is_file():
        return [f"Falta {path.name}"]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"{path.name}: YAML inválido: {exc}"]
    if not isinstance(data, dict) or not data.get("id"):
        errs.append(f"{path.name}: falta id")
    return errs


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    strict = "--strict" in sys.argv
    errors: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED:
        p = root / rel
        if not p.is_file():
            errors.append(f"Falta {rel}")
            continue
        if rel.endswith(".yml"):
            errors.extend(check_yaml_id(p))

    idx = root / "reglasEmpalme" / "component-index.yml"
    if idx.is_file():
        data = yaml.safe_load(idx.read_text(encoding="utf-8")) or {}
        n = len(data.get("components") or [])
        if n == 0:
            errors.append("component-index.yml vacío — ejecutar bootstrap-dsf-index.py")
        else:
            no_rule = sum(1 for c in data.get("components") or [] if not c.get("ruleId"))
            if no_rule:
                warnings.append(f"{no_rule} componentes sin ruleId (asignar en reglasActuacion)")

    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    for w in warnings:
        print(f"AVISO: {w}")

    if errors and strict:
        return 1
    print(f"OK: validate-dsf-structure ({len(errors)} errores, {len(warnings)} avisos)")
    return 1 if errors and strict else 0


if __name__ == "__main__":
    sys.exit(main())
