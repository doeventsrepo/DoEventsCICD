#!/usr/bin/env python3
"""Valida reglasEmpalme/ y bloque empalme: en reglasActuacion/."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML")
    sys.exit(1)

REQUIRED_EMPALME = {
    "reglasEmpalme/schema-capas.yml",
    "reglasEmpalme/routing-agentes.yml",
    "reglasEmpalme/port-map.yml",
}
VALID_TIERS = {"python", "cursor", "manual", "backend", "delegated"}
VALID_IMPACT = {"none", "minor", "major", ""}


def check_file(root: Path, rel: str) -> list[str]:
    warnings: list[str] = []
    path = root / rel
    if not path.is_file():
        return [f"Falta {rel}"]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("id"):
        warnings.append(f"{rel}: falta id")
    return warnings


def check_actuacion_empalme(path: Path) -> list[str]:
    warnings: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        warnings.append(f"{path.name}: YAML no parseable: {exc}")
        return warnings
    if not isinstance(data, dict):
        return warnings
    sources = data.get("source") or []
    if not sources:
        return warnings
    emp = data.get("empalme")
    if not emp:
        warnings.append(f"{path.name}: tiene source pero falta bloque empalme: (migrar a DSF v3.2)")
        return warnings
    tier = emp.get("agentTier")
    if tier and tier not in VALID_TIERS:
        warnings.append(f"{path.name}: agentTier inválido {tier}")
    layers = emp.get("layers") or {}
    for layer_name, layer_data in layers.items():
        if isinstance(layer_data, dict):
            impact = str(layer_data.get("impact", "none")).lower()
            if impact not in VALID_IMPACT:
                warnings.append(f"{path.name}: layers.{layer_name}.impact inválido")
    return warnings


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    strict = "--strict" in sys.argv
    warnings: list[str] = []

    for rel in REQUIRED_EMPALME:
        warnings.extend(check_file(root, rel))

    rules_dir = root / "reglasActuacion"
    if rules_dir.is_dir():
        for yml in sorted(rules_dir.rglob("*.yml")):
            warnings.extend(check_actuacion_empalme(yml))

    idx = root / "reglasEmpalme" / "component-index.yml"
    if idx.is_file():
        data = yaml.safe_load(idx.read_text(encoding="utf-8"))
        n = len(data.get("components") or [])
        if n == 0:
            warnings.append("component-index.yml vacío — Lovable debe poblar el índice")

    for w in warnings:
        print(f"AVISO: {w}")
    if strict and warnings:
        return 1
    print(f"OK: validate-empalme-rules ({len(warnings)} avisos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
