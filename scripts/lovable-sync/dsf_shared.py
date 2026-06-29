"""Utilidades compartidas del pipeline DSF v4."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ALL_LAYERS = (
    "diseno", "formulario", "campos", "logica", "navegacion", "backend",
    "seguridad", "performance", "accesibilidad", "responsive", "analytics",
)

# Fallback ruleId cuando bootstrap aún no generó component-index.yml
_PREFIX_RULE_ID: list[tuple[str, str]] = [
    ("src/components/events/", "eventos.crear.wizard"),
    ("src/components/feed/", "publicaciones.feed-principal"),
    ("src/components/stats/", "eventos.estadisticas"),
    ("src/components/admin/", "admin.panel"),
    ("src/components/tickets/", "tickets.compra.flow"),
    ("src/components/services/", "servicios.crear.wizard"),
    ("src/components/venues/", "lugares.crear.wizard"),
    ("src/components/chat/", "chat.privado"),
]

BACKEND_HINTS = re.compile(
    r"fetch\s*\(|axios\.|supabase|stripe|paypal|kyc|createUploadUrls|/api/",
    re.I,
)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def norm_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_component_index(lovable_root: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml(lovable_root / "reglasEmpalme" / "component-index.yml")
    index: dict[str, dict[str, Any]] = {}
    for entry in data.get("components") or []:
        lp = norm_path(str(entry.get("lovablePath", "")))
        if lp:
            index[lp] = entry
    return index


def load_port_map_yml(lovable_root: Path) -> dict[str, dict[str, Any]]:
    data = load_yaml(lovable_root / "reglasEmpalme" / "port-map.yml")
    index: dict[str, dict[str, Any]] = {}
    for entry in data.get("portMap") or []:
        lp = norm_path(str(entry.get("lovablePath", "")))
        if lp:
            index[lp] = entry
    return index


def load_web_port_map(web_root: Path) -> dict[str, str]:
    """Mapa exacto lovablePath → webPath (sin prefijos)."""
    path = web_root / ".lovable-port-map.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for entry in data.get("mapping") or data.get("mappings") or []:
        lp = norm_path(str(entry.get("lovable", entry.get("lovablePath", ""))))
        wp = norm_path(str(entry.get("web", entry.get("webPath", ""))))
        if lp and wp and not lp.endswith("/"):
            mapping[lp] = wp
    return mapping


def resolve_web_path_from_port_map(rel: str, web_root: Path) -> str:
    """Resuelve ruta WEB con entradas exactas y prefijos del port-map."""
    exact = load_web_port_map(web_root).get(rel, "")
    if exact:
        return exact
    try:
        from port_map_utils import load_port_map, map_lovable_to_web

        return map_lovable_to_web(rel, load_port_map(web_root / ".lovable-port-map.json")) or ""
    except ImportError:
        return ""


def load_backend_endpoints(lovable_root: Path) -> list[dict[str, Any]]:
    data = load_yaml(lovable_root / "contratosBackend" / "endpoints.yml")
    return list(data.get("endpoints") or [])


def changed_ui_paths(manifest: dict[str, Any]) -> list[str]:
    return [
        norm_path(f.get("path", ""))
        for f in manifest.get("changedFiles", [])
        if f.get("kind") == "ui" and f.get("path")
    ]


def resolve_web_path(
    lovable_path: str,
    *,
    lovable_root: Path,
    web_root: Path,
) -> tuple[str, str, dict[str, Any]]:
    rel = norm_path(lovable_path)
    meta: dict[str, Any] = {"lovablePath": rel}

    idx = load_component_index(lovable_root).get(rel, {})
    pm = load_port_map_yml(lovable_root).get(rel, {})
    web_map = load_web_port_map(web_root)

    web_path = (
        idx.get("webPath")
        or pm.get("webPath")
        or web_map.get(rel)
        or resolve_web_path_from_port_map(rel, web_root)
        or ""
    )
    meta["ruleId"] = idx.get("ruleId") or pm.get("ruleId") or ""
    meta["agentTier"] = idx.get("agentTier") or pm.get("agentTier") or "python"
    meta["domain"] = idx.get("domain") or pm.get("domain") or ""
    meta["status"] = pm.get("status") or ("mapped" if web_path else "pending")
    meta["duplicateCheck"] = pm.get("duplicateCheck", "unknown")
    meta["existingEquivalent"] = pm.get("existingEquivalent", "")

    if pm.get("status") in ("blocked", "delegated"):
        meta["status"] = pm["status"]
    elif not web_path:
        meta["status"] = "blocked"
    elif not meta["ruleId"]:
        meta["status"] = "pending"
        for prefix, rule_id in _PREFIX_RULE_ID:
            if rel.startswith(prefix) or rel == prefix.rstrip("/"):
                meta["ruleId"] = rule_id
                break

    return norm_path(str(web_path)), str(meta["status"]), meta


def compute_file_risk(
    *,
    layers: list[str],
    agent_tier: str,
    web_status: str,
    has_rule_id: bool,
    backend_required: bool = False,
    package_changed: bool = False,
    duplicate_risk: bool = False,
) -> str:
    if web_status == "blocked" or not has_rule_id or duplicate_risk:
        return "blocked"
    if backend_required or agent_tier == "backend":
        return "high"
    if package_changed or agent_tier == "cursor":
        return "high"
    if any(l in layers for l in ("backend", "seguridad", "logica")):
        return "high"
    if any(l in layers for l in ("formulario", "campos", "navegacion")):
        return "medium"
    return "low"


def aggregate_risk(levels: list[str]) -> str:
    order = {"blocked": 4, "high": 3, "medium": 2, "low": 1}
    best = "low"
    for lvl in levels:
        if order.get(lvl, 0) > order.get(best, 0):
            best = lvl
    return best
