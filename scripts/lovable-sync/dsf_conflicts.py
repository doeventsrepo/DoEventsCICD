"""Resolución de conflictos DSF — jerarquía de verdad."""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None

TRUTH_HIERARCHY = [
    "DoEventsWEB",
    "contratosBackend",
    "reglasActuacion",
    "reglasEmpalme",
    "Lovable",
]


def norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_index(lovable_root: Path) -> dict[str, dict[str, Any]]:
    data = _load(lovable_root / "reglasEmpalme" / "component-index.yml")
    out: dict[str, dict[str, Any]] = {}
    for e in data.get("components") or []:
        lp = norm(str(e.get("lovablePath", "")))
        if lp:
            out[lp] = e
    return out


def load_port_map(lovable_root: Path) -> dict[str, dict[str, Any]]:
    data = _load(lovable_root / "reglasEmpalme" / "port-map.yml")
    out: dict[str, dict[str, Any]] = {}
    for e in data.get("portMap") or []:
        lp = norm(str(e.get("lovablePath", "")))
        if lp:
            out[lp] = e
    return out


def load_rules_sources(lovable_root: Path) -> dict[str, dict[str, Any]]:
    """lovablePath → regla que lo declara en source."""
    out: dict[str, dict[str, Any]] = {}
    rules_dir = lovable_root / "reglasActuacion"
    if not rules_dir.is_dir() or yaml is None:
        return out
    for yml in rules_dir.rglob("*.yml"):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        rid = data.get("id", "")
        emp = data.get("empalme") or {}
        for src in data.get("source") or []:
            s = norm(str(src))
            out[s] = {"ruleId": rid, "empalme": emp, "rulePath": yml.relative_to(lovable_root).as_posix()}
    return out


def detect_conflicts(
    lovable_root: Path,
    web_root: Path,
    ui_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Detecta conflictos index ↔ port-map ↔ reglas ↔ WEB."""
    conflicts: list[dict[str, Any]] = []
    index = load_index(lovable_root)
    port_map = load_port_map(lovable_root)
    rules_src = load_rules_sources(lovable_root)
    check_paths = ui_paths if ui_paths else sorted(set(index) | set(port_map))

    for lp in check_paths:
        lp = norm(lp)
        idx = index.get(lp, {})
        pm = port_map.get(lp, {})
        rule = rules_src.get(lp, {})

        if lp in index and lp in port_map:
            for field in ("webPath", "ruleId"):
                iv, pv = norm(str(idx.get(field, ""))), norm(str(pm.get(field, "")))
                if iv and pv and iv != pv:
                    conflicts.append({
                        "lovablePath": lp,
                        "type": f"index_vs_portmap_{field}",
                        "index": iv,
                        "portMap": pv,
                        "resolution": "blocked",
                        "winner": "reglasEmpalme",
                        "note": "Unificar manualmente — index y port-map deben coincidir",
                    })

        emp_rule_id = str(rule.get("ruleId", ""))
        idx_rule_id = str(idx.get("ruleId", ""))
        if emp_rule_id and idx_rule_id and emp_rule_id != idx_rule_id:
            conflicts.append({
                "lovablePath": lp,
                "type": "reglasActuacion_vs_index_ruleId",
                "reglasActuacion": emp_rule_id,
                "componentIndex": idx_rule_id,
                "resolution": "blocked",
                "winner": "reglasActuacion",
            })

        emp = rule.get("empalme") or {}
        emp_web = norm(str(emp.get("webPath", "")))
        emp_lp = norm(str(emp.get("lovablePath", "")))
        idx_web = norm(str(idx.get("webPath", "")))
        # webPath en regla multi-source = página contenedora; destino por componente vive en index/port-map
        if emp_web and idx_web and emp_web != idx_web:
            if emp_lp and emp_lp != lp:
                pass  # empalme de otra unidad — no comparar
            elif idx_web and norm(str(pm.get("webPath", ""))) == idx_web:
                # Bootstrap alineó index/port-map desde DoEventsWEB; regla empalme puede estar desactualizada.
                conflicts.append({
                    "lovablePath": lp,
                    "type": "empalme_vs_index_webPath",
                    "empalme": emp_web,
                    "componentIndex": idx_web,
                    "resolution": "manual-review",
                    "winner": "reglasEmpalme",
                    "note": "Regla empalme.webPath desactualizada — index/port-map manda",
                })
            elif emp_lp == lp or (not emp_lp and not emp_web.endswith("Page.tsx")):
                conflicts.append({
                    "lovablePath": lp,
                    "type": "empalme_vs_index_webPath",
                    "empalme": emp_web,
                    "componentIndex": idx_web,
                    "resolution": "blocked",
                    "winner": "reglasActuacion",
                })
            elif emp_web.endswith("Page.tsx") and "/lovable/components/" in idx_web:
                pass  # regla página + index componente — esperado, index/port-map manda
            else:
                conflicts.append({
                    "lovablePath": lp,
                    "type": "empalme_vs_index_webPath",
                    "empalme": emp_web,
                    "componentIndex": idx_web,
                    "resolution": "manual-review",
                    "winner": "reglasEmpalme",
                    "note": "Unificar webPath en regla o index",
                })

        web_path = idx_web or emp_web or norm(str(pm.get("webPath", "")))
        if web_path:
            full_web = web_root / web_path
            if not full_web.is_file() and lp.startswith("src/components/"):
                # Nuevo componente permitido si status pending/mapped en port-map
                st = str(pm.get("status", idx.get("status", "mapped")))
                if st not in ("pending", "mapped"):
                    conflicts.append({
                        "lovablePath": lp,
                        "type": "webPath_missing_in_DoEventsWEB",
                        "webPath": web_path,
                        "resolution": "manual-review",
                        "winner": "DoEventsWEB",
                    })

    return conflicts


def has_blocking_conflicts(conflicts: list[dict[str, Any]]) -> bool:
    return any(c.get("resolution") == "blocked" for c in conflicts)
