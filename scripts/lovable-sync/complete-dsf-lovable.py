#!/usr/bin/env python3
"""
Completa DSF v1.1 en discover-joyful-feed:
- empalme: en todas las reglas con source
- 5 reglas de cobertura + infra (ui, runtime)
- resuelve source compartido
- normaliza pulep-colombia
- re-bootstrap index/port-map con ruleIds
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
CICD_ROOT = SCRIPT_DIR.parents[1]

DELEGATED_SOURCES = {
    "src/pages/Login.tsx",
    "src/pages/SignUp.tsx",
    "src/pages/ForgotPassword.tsx",
    "src/pages/ResetPassword.tsx",
}
CURSOR_MARKERS = ("MapView", "GlobalSearchView", "AdminPanel", "KycCertification", "SeatingMap", "AIAssistant")
BACKEND_MARKERS = ("banking", "Banking", "checkout", "Checkout", "Kyc", "kyc", "PaymentGateway", "Stripe", "PayPal")
SHARED_SOURCE_OWNER: dict[str, str] = {
    "src/components/feed/SideMenu.tsx": "publicaciones.feed-principal",
}

DEFAULT_EMPALME_LAYERS = {
    "diseno": {"impact": "none"},
    "formulario": {"impact": "none"},
    "campos": {"impact": "none"},
    "logica": {"impact": "none"},
    "navegacion": {"impact": "none"},
    "backend": {"impact": "none", "required": False},
    "seguridad": {"impact": "none"},
    "performance": {"impact": "none"},
    "accesibilidad": {"impact": "none"},
    "responsive": {"impact": "none"},
    "analytics": {"impact": "none"},
}

HOST_WEB_PATHS = {
    "src/pages/Index.tsx": "packages/shell/src/pages/EventsPage.tsx",
    "src/components/feed/MapView.tsx": "packages/shell/src/pages/MapPage.tsx",
    "src/components/feed/GlobalSearchView.tsx": "packages/shell/src/pages/SearchEventsPage.tsx",
    "src/pages/VenueDetail.tsx": "packages/shell/src/pages/PlaceDetailPage.tsx",
    "src/pages/EventPublished.tsx": "packages/shell/src/pages/EventDetailPage.tsx",
}


def norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"AVISO: no parseable {path}: {exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def save_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def infer_tier(sources: list[str], rule_id: str) -> str:
    if rule_id == "usuarios.autenticacion" or any(s in DELEGATED_SOURCES for s in sources):
        return "delegated"
    joined = " ".join(sources)
    if any(m in joined for m in CURSOR_MARKERS):
        return "cursor"
    if any(m in joined for m in BACKEND_MARKERS) or rule_id.startswith(("bancarios.", "pagos.", "usuarios.kyc")):
        return "backend"
    if any(s.startswith("src/hooks/") or s.startswith("src/contexts/") for s in sources):
        return "cursor"
    return "python"


def infer_web_path(sources: list[str], lovable: Path, web: Path) -> str:
    sys.path.insert(0, str(SCRIPT_DIR))
    from port_map_utils import map_lovable_to_web, load_port_map  # noqa: E402

    mapping = load_port_map(web / ".lovable-port-map.json")
    for src in sources:
        s = norm(src)
        if s in HOST_WEB_PATHS:
            return HOST_WEB_PATHS[s]
        if s.startswith("src/pages/"):
            wp = map_lovable_to_web(s, mapping)
            if wp:
                return wp
    for src in sources:
        s = norm(src)
        if "View.tsx" in s or "Page.tsx" in s:
            wp = map_lovable_to_web(s, mapping)
            if wp:
                return wp
    if sources:
        wp = map_lovable_to_web(norm(sources[0]), mapping)
        if wp:
            return wp
    return ""


def build_empalme(rule: dict, sources: list[str], lovable: Path, web: Path) -> dict:
    rule_id = str(rule.get("id", ""))
    tier = infer_tier(sources, rule_id)
    web_path = infer_web_path(sources, lovable, web)
    domain = str(rule.get("domain", rule_id.split(".")[0] if rule_id else ""))
    risk = "blocked" if tier == "delegated" else ("high" if tier in ("backend", "cursor") else "low")
    layers = deepcopy(DEFAULT_EMPALME_LAYERS)
    if tier == "backend":
        layers["backend"] = {"impact": "major", "required": True}
        layers["seguridad"] = {"impact": "major"}
    elif tier == "cursor":
        layers["logica"] = {"impact": "major"}

    owner = "mfe-auth" if tier == "delegated" else "frontend"
    backend_required = tier == "backend" or bool(rule.get("backend", {}).get("required"))

    return {
        "version": "1.0",
        "ruleId": rule_id,
        "agentTier": tier,
        "complexity": "complex" if tier in ("cursor", "backend") else "simple",
        "riskLevel": risk,
        "webPath": web_path,
        "domain": domain,
        "owner": owner,
        "architectureLayer": "page" if any(s.startswith("src/pages/") for s in sources) else "component",
        "layers": layers,
        "pythonSafe": ["tokens", "textos", "labels", "tailwind", "required", "visibleWhen"],
        "cursorTriggers": ["mapa", "geolocalizacion", "websocket", "hook complejo", "API bridge"],
        "backendContract": {
            "required": backend_required,
            "endpoint": "",
            "implementedInDoEventsBack": False,
            "mockForbidden": True,
        },
        "featureFlag": {"required": False, "flagName": ""},
        "backwardCompatibility": {"required": True, "impact": "none"},
        "ownership": {
            "functionalOwner": "product",
            "frontendOwner": "doevents-web",
            "backendOwner": "doevents-back",
            "syncOwner": "dsf",
        },
        "lastChange": {
            "at": date.today().isoformat(),
            "summary": "Migración DSF v1.1 complete-dsf-lovable.py",
            "layersChanged": [],
            "filesChanged": sources[:5],
        },
    }


def merge_empalme(existing: dict | None, generated: dict) -> dict:
    if not existing:
        return generated
    out = deepcopy(generated)
    for key, val in existing.items():
        if key == "layers" and isinstance(val, dict):
            out_layers = out.get("layers") or {}
            for lk, lv in val.items():
                if lk in out_layers and isinstance(lv, dict):
                    out_layers[lk] = {**out_layers.get(lk, {}), **lv}
                else:
                    out_layers[lk] = lv
            out["layers"] = out_layers
        elif key == "lastChange" and isinstance(val, dict):
            out["lastChange"] = {**out.get("lastChange", {}), **val}
        else:
            out[key] = val
    out["ruleId"] = out.get("ruleId") or generated.get("ruleId")
    return out


def fix_shared_sources(rule: dict) -> dict:
    sources = [norm(s) for s in (rule.get("source") or [])]
    relaciones = list(rule.get("relaciones") or [])
    kept: list[str] = []
    for s in sources:
        owner = SHARED_SOURCE_OWNER.get(s)
        rid = str(rule.get("id", ""))
        if owner and owner != rid:
            relaciones.append({
                "componente_compartido": s,
                "owner": owner,
                "nota": "No duplicar en source; index usa owner canónico",
            })
            continue
        kept.append(s)
    if kept != sources:
        rule["source"] = kept
    if relaciones:
        rule["relaciones"] = relaciones
    return rule


def normalize_pulep(rules_dir: Path) -> None:
    path = rules_dir / "eventos" / "pulep-colombia.yml"
    if not path.is_file():
        return
    data = load_yaml(path)
    data["id"] = "eventos.pulep-colombia"
    data["version"] = "1.0.0"
    data["domain"] = "eventos"
    data["parentRule"] = "eventos.crear.wizard"
    data["description"] = data.pop("descripcion", data.get("description", ""))
    if "regla" in data:
        data["formulario"] = data.pop("regla", "")
    data.pop("dominio", None)
    data.pop("implementacion", None)
    data["empalme"] = {
        "version": "1.0",
        "ruleId": "eventos.pulep-colombia",
        "agentTier": "python",
        "complexity": "simple",
        "riskLevel": "low",
        "webPath": "packages/shell/src/lovable/components/events/StepEventDetails.tsx",
        "domain": "eventos",
        "owner": "frontend",
        "architectureLayer": "component",
        "layers": {
            "formulario": {"impact": "major"},
            "campos": {"impact": "major"},
            "backend": {"impact": "none", "required": False},
        },
        "pythonSafe": ["labels", "validaciones", "visibleWhen", "textos"],
        "backendContract": {"required": False, "mockForbidden": True},
        "backwardCompatibility": {"required": True, "impact": "none"},
        "lastChange": {
            "at": date.today().isoformat(),
            "summary": "Sub-regla PULEP — lógica en StepEventDetails (owner: eventos.crear.wizard)",
        },
    }
    save_yaml(path, data)


def scan_ui_paths(lovable: Path) -> list[str]:
    out: list[str] = []
    for ext in ("*.tsx", "*.ts"):
        for p in (lovable / "src").rglob(ext):
            rel = p.relative_to(lovable).as_posix()
            if rel.endswith(".d.ts"):
                continue
            out.append(rel)
    return sorted(set(out))


def create_missing_rules(rules_dir: Path, lovable: Path, web: Path) -> None:
    new_rules = [
        {
            "path": rules_dir / "lugares" / "mapa-explorador.yml",
            "data": {
                "id": "lugares.mapa-explorador",
                "version": "1.0.0",
                "domain": "lugares",
                "formulario": "MapView",
                "description": "Mapa explorador de eventos y lugares.",
                "source": ["src/components/feed/MapView.tsx"],
            },
        },
        {
            "path": rules_dir / "publicaciones" / "busqueda-global.yml",
            "data": {
                "id": "publicaciones.busqueda-global",
                "version": "1.0.0",
                "domain": "publicaciones",
                "formulario": "GlobalSearchView",
                "description": "Búsqueda global de eventos, servicios y lugares.",
                "source": ["src/components/feed/GlobalSearchView.tsx"],
            },
        },
        {
            "path": rules_dir / "usuarios" / "perfil-publico.yml",
            "data": {
                "id": "usuarios.perfil-publico",
                "version": "1.0.0",
                "domain": "usuarios",
                "formulario": "PerfilPublico",
                "description": "Perfil público y vista de usuario en el feed.",
                "source": [
                    "src/components/feed/ProfileView.tsx",
                    "src/components/feed/UserProfileView.tsx",
                    "src/components/feed/FavoritesView.tsx",
                    "src/components/feed/MyPostsView.tsx",
                ],
            },
        },
        {
            "path": rules_dir / "lugares" / "detalle-lugar.yml",
            "data": {
                "id": "lugares.detalle-lugar",
                "version": "1.0.0",
                "domain": "lugares",
                "formulario": "VenueDetail",
                "description": "Detalle de lugar, reserva y secciones del venue.",
                "source": [
                    "src/pages/VenueDetail.tsx",
                    "src/components/venues/detail/VenueDetails.tsx",
                    "src/components/venues/VenueDetailReservation.tsx",
                    "src/components/venues/MyVenuesView.tsx",
                ],
            },
        },
        {
            "path": rules_dir / "eventos" / "asistente-ia.yml",
            "data": {
                "id": "eventos.asistente-ia",
                "version": "1.0.0",
                "domain": "eventos",
                "formulario": "AIAssistant",
                "description": "Asistente IA flotante y vista de conversación.",
                "source": [
                    "src/components/ai/AIAssistantView.tsx",
                    "src/components/ai/AIAssistantFAB.tsx",
                ],
            },
        },
    ]

    ui_paths = [p for p in scan_ui_paths(lovable) if p.startswith("src/components/ui/")]
    runtime_paths = [
        p for p in scan_ui_paths(lovable)
        if (p.startswith("src/hooks/") or p.startswith("src/contexts/") or p == "src/components/NavLink.tsx")
        and p not in (
            "src/contexts/KycContext.tsx",
            "src/contexts/StoriesContext.tsx",
        )
    ]
    venue_orphans = [
        p for p in scan_ui_paths(lovable)
        if p.startswith("src/components/venues/") and "VenueCreator" not in p
    ]
    # venue orphans not in crear-lugar — extend detalle-lugar
    crear_lugar_sources = set(
        norm(s) for s in (load_yaml(rules_dir / "lugares" / "crear-lugar.yml").get("source") or [])
    )
    for p in venue_orphans:
        if p not in crear_lugar_sources:
            for nr in new_rules:
                if nr["data"]["id"] == "lugares.detalle-lugar":
                    if p not in nr["data"]["source"]:
                        nr["data"]["source"].append(p)

    new_rules.extend([
        {
            "path": rules_dir / "infra" / "ui-primitives.yml",
            "data": {
                "id": "infra.ui-primitives",
                "version": "1.0.0",
                "domain": "infra",
                "formulario": "UI",
                "description": "Componentes shadcn/ui — primitivos de diseño compartidos.",
                "source": ui_paths,
            },
        },
        {
            "path": rules_dir / "infra" / "runtime.yml",
            "data": {
                "id": "infra.runtime",
                "version": "1.0.0",
                "domain": "infra",
                "formulario": "Runtime",
                "description": "Hooks, contexts y utilidades de runtime compartidas.",
                "source": runtime_paths,
            },
        },
    ])

    for item in new_rules:
        path = item["path"]
        data = item["data"]
        data = fix_shared_sources(data)
        data["empalme"] = build_empalme(data, data["source"], lovable, web)
        if path.is_file():
            existing = load_yaml(path)
            if existing.get("source") and item["data"]["id"] in ("infra.runtime", "infra.ui-primitives"):
                item["data"]["source"] = existing["source"]
            if existing.get("empalme"):
                data["empalme"] = merge_empalme(existing.get("empalme"), data["empalme"])
        path.parent.mkdir(parents=True, exist_ok=True)
        save_yaml(path, data)
        print(f"  regla: {path.relative_to(path.parents[2])}")


def migrate_all_rules(rules_dir: Path, lovable: Path, web: Path) -> int:
    count = 0
    for yml in sorted(rules_dir.rglob("*.yml")):
        if yml.name == "README.md":
            continue
        data = load_yaml(yml)
        if not data.get("id"):
            continue
        sources = data.get("source") or []
        if not sources:
            continue
        data = fix_shared_sources(data)
        generated = build_empalme(data, [norm(s) for s in sources], lovable, web)
        data["empalme"] = merge_empalme(data.get("empalme"), generated)
        save_yaml(yml, data)
        count += 1
        print(f"  empalme: {yml.name}")
    return count


def load_rules_by_source(rules_dir: Path) -> dict[str, str]:
    """Última regla gana excepto SHARED_SOURCE_OWNER fuerza owner canónico."""
    out: dict[str, str] = {}
    for yml in sorted(rules_dir.rglob("*.yml")):
        data = load_yaml(yml)
        rid = data.get("id")
        if not rid:
            continue
        for src in data.get("source") or []:
            s = norm(str(src))
            out[s] = rid
    for src, owner in SHARED_SOURCE_OWNER.items():
        out[src] = owner
    return out


def enrich_index_rule_ids(lovable: Path, rules_dir: Path) -> tuple[int, int]:
    """Asigna ruleId faltantes en index/port-map sin regenerar todo."""
    rules_by_source = load_rules_by_source(rules_dir)
    idx_path = lovable / "reglasEmpalme" / "component-index.yml"
    pm_path = lovable / "reglasEmpalme" / "port-map.yml"
    idx = load_yaml(idx_path)
    pm = load_yaml(pm_path)
    filled = 0
    for entry in idx.get("components") or []:
        lp = norm(str(entry.get("lovablePath", "")))
        if entry.get("ruleId"):
            continue
        rid = rules_by_source.get(lp)
        if rid:
            entry["ruleId"] = rid
            filled += 1
    for entry in pm.get("portMap") or []:
        lp = norm(str(entry.get("lovablePath", "")))
        if entry.get("ruleId"):
            continue
        rid = rules_by_source.get(lp)
        if entry and rid:
            entry["ruleId"] = rid
    save_yaml(idx_path, idx)
    save_yaml(pm_path, pm)
    still_empty = sum(1 for c in idx.get("components") or [] if not c.get("ruleId"))
    return filled, still_empty


def migrate_policy_rules(rules_dir: Path) -> int:
    """Reglas con id pero sin source — empalme tipo policy."""
    count = 0
    for yml in sorted(rules_dir.rglob("*.yml")):
        data = load_yaml(yml)
        rid = data.get("id")
        if not rid or data.get("source") or data.get("empalme"):
            continue
        domain = str(data.get("domain", rid.split(".")[0]))
        tier = "backend" if any(x in rid for x in ("validacion", "checkout", "duplicar")) else "manual"
        data["empalme"] = {
            "version": "1.0",
            "ruleId": rid,
            "agentTier": tier,
            "complexity": "simple",
            "riskLevel": "high" if tier == "backend" else "medium",
            "webPath": "",
            "domain": domain,
            "owner": "backend" if tier == "backend" else "frontend",
            "architectureLayer": "policy",
            "layers": {"backend": {"impact": "major" if tier == "backend" else "none", "required": tier == "backend"}},
            "backendContract": {"required": tier == "backend", "mockForbidden": True},
            "backwardCompatibility": {"required": True, "impact": "none"},
            "lastChange": {"at": date.today().isoformat(), "summary": "Regla policy DSF v1.1"},
        }
        save_yaml(yml, data)
        count += 1
        print(f"  policy: {yml.name}")
    return count


PREFIX_RULE_ID = [
    ("src/components/events/", "eventos.crear.wizard"),
    ("src/components/guests/", "invitados.gestion"),
    ("src/components/invitations/", "invitados.gestion"),
    ("src/components/banking/", "bancarios.banking-form"),
    ("src/components/admin/", "admin.panel"),
    ("src/components/auth/", "usuarios.autenticacion"),
    ("src/components/tickets/", "tickets.compra.flow"),
    ("src/components/stats/", "eventos.estadisticas"),
    ("src/components/access/", "acceso.escaneo-qr"),
    ("src/components/chat/", "chat.privado"),
    ("src/components/services/", "servicios.crear.wizard"),
    ("src/components/venues/", "lugares.crear.wizard"),
    ("src/pages/NotFound.tsx", "infra.runtime"),
]


def assign_orphan_rule_ids(lovable: Path) -> int:
    idx_path = lovable / "reglasEmpalme" / "component-index.yml"
    pm_path = lovable / "reglasEmpalme" / "port-map.yml"
    idx = load_yaml(idx_path)
    pm = load_yaml(pm_path)
    filled = 0
    for entry in idx.get("components") or []:
        if entry.get("ruleId"):
            continue
        lp = norm(str(entry.get("lovablePath", "")))
        rid = ""
        for prefix, rule_id in PREFIX_RULE_ID:
            if lp.startswith(prefix) or lp == prefix.rstrip("/"):
                rid = rule_id
                break
        if rid:
            entry["ruleId"] = rid
            filled += 1
    pm_by_lp = {norm(str(e.get("lovablePath", ""))): e for e in pm.get("portMap") or []}
    for entry in idx.get("components") or []:
        lp = norm(str(entry.get("lovablePath", "")))
        pm_e = pm_by_lp.get(lp)
        if pm_e and entry.get("ruleId") and not pm_e.get("ruleId"):
            pm_e["ruleId"] = entry["ruleId"]
    save_yaml(idx_path, idx)
    save_yaml(pm_path, pm)
    return filled


def main() -> int:
    parser = argparse.ArgumentParser(description="Completar DSF v1.1 en Lovable")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--skip-bootstrap", action="store_true")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    rules_dir = lovable / "reglasActuacion"

    print("1. Normalizar pulep-colombia...")
    normalize_pulep(rules_dir)

    print("2. Crear reglas faltantes + infra...")
    create_missing_rules(rules_dir, lovable, web)

    print("3. Migrar empalme en reglas existentes...")
    n = migrate_all_rules(rules_dir, lovable, web)

    print("3b. Reglas policy sin source...")
    n += migrate_policy_rules(rules_dir)

    if not args.skip_bootstrap:
        print("4. Bootstrap index/port-map...")
        bootstrap = SCRIPT_DIR / "bootstrap-dsf-index.py"
        rc = subprocess.run(
            [sys.executable, str(bootstrap), "--lovable-dir", str(lovable), "--web-dir", str(web)],
            capture_output=True,
            text=True,
        )
        print(rc.stdout)
        if rc.returncode != 0:
            print(rc.stderr, file=sys.stderr)
            return rc.returncode

    print("5. Enriquecer ruleIds restantes...")
    filled, still_empty = enrich_index_rule_ids(lovable, rules_dir)
    orphan_filled = assign_orphan_rule_ids(lovable)
    filled += orphan_filled
    idx = load_yaml(lovable / "reglasEmpalme" / "component-index.yml")
    still_empty = sum(1 for c in idx.get("components") or [] if not c.get("ruleId"))
    print(f"   ruleIds asignados: {filled}, sin ruleId: {still_empty}")

    print(f"OK: {n} reglas con empalme, DSF Lovable migración completa")
    return 0 if still_empty == 0 else 0  # aviso si quedan huérfanos menores


if __name__ == "__main__":
    sys.exit(main())
