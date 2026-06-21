"""Validación idempotencia DSF — entradas duplicadas en YAML e índices."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def check_index_port_map_idempotency(lovable_root: Path) -> list[str]:
    """Detecta lovablePath/webPath duplicados en component-index y port-map."""
    errors: list[str] = []
    idx = _load(lovable_root / "reglasEmpalme" / "component-index.yml")
    pm = _load(lovable_root / "reglasEmpalme" / "port-map.yml")

    for label, key, entries in (
        ("component-index", "components", idx.get("components") or []),
        ("port-map", "portMap", pm.get("portMap") or []),
    ):
        seen_lp: dict[str, int] = {}
        seen_wp: dict[str, int] = {}
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            lp = norm(str(entry.get("lovablePath", "")))
            wp = norm(str(entry.get("webPath", "")))
            if lp:
                seen_lp[lp] = seen_lp.get(lp, 0) + 1
            if wp:
                seen_wp[wp] = seen_wp.get(wp, 0) + 1
        for lp, n in seen_lp.items():
            if n > 1:
                errors.append(f"{label}: lovablePath duplicado ({n}x): {lp}")
        for wp, n in seen_wp.items():
            if n > 1:
                errors.append(f"{label}: webPath duplicado ({n}x): {wp}")

    return errors


def check_rules_source_duplicates(lovable_root: Path) -> list[str]:
    """source: compartido entre reglas — aviso (resolver en Lovable)."""
    warnings: list[str] = []
    source_to_rules: dict[str, list[str]] = {}
    rules_dir = lovable_root / "reglasActuacion"
    if not rules_dir.is_dir() or yaml is None:
        return warnings
    for yml in rules_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        rid = str(data.get("id", yml.stem))
        for src in data.get("source") or []:
            source_to_rules.setdefault(norm(str(src)), []).append(rid)
    for src, rules in source_to_rules.items():
        if len(rules) > 1:
            warnings.append(f"source compartido: {src} -> {rules}")
    return warnings


def check_empalme_blocks(lovable_root: Path) -> list[str]:
    """YAML con source: debe tener bloque empalme (avisos hasta migración)."""
    warnings: list[str] = []
    rules_dir = lovable_root / "reglasActuacion"
    if not rules_dir.is_dir() or yaml is None:
        return warnings
    for yml in rules_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if data.get("source") and not data.get("empalme"):
            warnings.append(f"{yml.relative_to(lovable_root)}: source sin empalme")
    return warnings


def run_all(lovable_root: Path) -> dict[str, Any]:
    errors = check_index_port_map_idempotency(lovable_root)
    warnings = check_empalme_blocks(lovable_root)
    warnings.extend(check_rules_source_duplicates(lovable_root))
    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "errorCount": len(errors),
        "warningCount": len(warnings),
    }
