#!/usr/bin/env python3
"""Resuelve reglas de empalme por ruta Lovable — capas, tier agente, backend."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

TIER_MAP = {
    "python": "python",
    "cursor": "cursor",
    "manual": "manual",
    "backend": "backend",
    "delegated": "skipped",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def load_component_index(lovable_root: Path) -> dict[str, dict[str, Any]]:
    data = _load_yaml(lovable_root / "reglasEmpalme" / "component-index.yml")
    index: dict[str, dict[str, Any]] = {}
    for entry in data.get("components") or []:
        lp = _norm(entry.get("lovablePath", ""))
        if lp:
            index[lp] = entry
    return index


def load_rules_by_source(lovable_root: Path) -> dict[str, list[dict[str, Any]]]:
    """Mapa lovablePath → lista de reglas que lo referencian en source:."""
    rules_dir = lovable_root / "reglasActuacion"
    by_source: dict[str, list[dict[str, Any]]] = {}
    if not rules_dir.is_dir() or yaml is None:
        return by_source

    for yml in rules_dir.rglob("*.yml"):
        data = _load_yaml(yml)
        if not data.get("id"):
            continue
        data["_rulePath"] = yml.relative_to(lovable_root).as_posix()
        for src in data.get("source") or []:
            src = _norm(str(src))
            by_source.setdefault(src, []).append(data)
            # Prefijo carpeta: src/components/feed/ → match files inside
            if src.endswith("/"):
                by_source.setdefault(src.rstrip("/"), []).append(data)
    return by_source


def _match_rules(lovable_path: str, by_source: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rel = _norm(lovable_path)
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern, rules in by_source.items():
        if rel == pattern or rel.startswith(pattern + "/") or pattern.startswith(rel):
            for r in rules:
                rid = r.get("id", "")
                if rid not in seen:
                    seen.add(rid)
                    matched.append(r)
    return matched


def extract_empalme_block(rule: dict[str, Any]) -> dict[str, Any]:
    return rule.get("empalme") or {}


def layers_from_rule(rule: dict[str, Any]) -> list[str]:
    emp = extract_empalme_block(rule)
    layers_obj = emp.get("layers") or {}
    active: list[str] = []
    for layer_name, layer_data in layers_obj.items():
        if not isinstance(layer_data, dict):
            continue
        impact = str(layer_data.get("impact", "none")).lower()
        if impact not in ("none", ""):
            active.append(layer_name)
    if not active and rule.get("campos"):
        active.append("campos")
    if not active and rule.get("formulario"):
        active.append("formulario")
    if rule.get("acciones"):
        for _name, action in (rule.get("acciones") or {}).items():
            if isinstance(action, dict) and action.get("backend"):
                active.append("backend")
                break
    return active or ["logica"]


def resolve_agent_tier(
    lovable_path: str,
    lovable_root: Path,
    *,
    default_tier: str = "python",
) -> dict[str, Any]:
    """Resuelve tier agente y capas para una ruta Lovable."""
    rel = _norm(lovable_path)
    index = load_component_index(lovable_root)
    by_source = load_rules_by_source(lovable_root)

    entry = index.get(rel, {})
    rules = _match_rules(rel, by_source)

    tier = entry.get("agentTier") or default_tier
    complexity = entry.get("complexity", "simple")
    layers = list(entry.get("layers") or [])
    rule_ids: list[str] = []
    backend_required = False
    cursor_triggers: list[str] = []
    summaries: list[str] = []

    for rule in rules:
        rule_ids.append(str(rule.get("id", "")))
        emp = extract_empalme_block(rule)
        if emp.get("agentTier"):
            tier = emp["agentTier"]
        if emp.get("complexity"):
            complexity = emp["complexity"]
        layers.extend(layers_from_rule(rule))
        if emp.get("backend", {}).get("required"):
            backend_required = True
        cursor_triggers.extend(emp.get("cursorTriggers") or [])
        lc = emp.get("lastChange") or {}
        if lc.get("summary"):
            summaries.append(str(lc["summary"]))

    if backend_required or "backend" in layers:
        tier = "backend"
    elif tier == "python" and complexity == "complex":
        tier = "cursor"
    elif any(p in rel for p in ("MapView", "GlobalSearch", "AdminPanel", "KycCertification")):
        if tier == "python":
            tier = "cursor"

    try:
        from quality_policy import load_quality_policy

        fp = load_quality_policy(lovable_root).get("forbiddenPatterns") or {}
        for p in fp.get("cursorOnlyPaths") or []:
            if rel.startswith(p) or p.rstrip("/") in rel:
                tier = "cursor"
                break
    except ImportError:
        pass

    layers = sorted(set(layers))
    return {
        "lovablePath": rel,
        "ruleIds": rule_ids,
        "agentTier": TIER_MAP.get(tier, tier),
        "complexity": complexity,
        "layers": layers,
        "backendRequired": backend_required,
        "cursorTriggers": cursor_triggers,
        "summaries": summaries,
        "fromIndex": bool(entry),
        "fromRules": len(rules),
    }


def build_change_manifest_enriched(
    lovable_root: Path,
    changed_paths: list[str],
) -> list[dict[str, Any]]:
    """Enriquece cada path del diff con capas y tier para agentes."""
    enriched: list[dict[str, Any]] = []
    for path in changed_paths:
        info = resolve_agent_tier(path, lovable_root)
        enriched.append(info)
    return enriched
