#!/usr/bin/env python3
"""Enlaza reglas DSF (reglasActuacion) con endpoints en contratosBackend/endpoints.yml."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# webKeys explícitos por regla (override)
RULE_WEBKEYS: dict[str, list[str]] = {
    "publicaciones.feed-principal": ["wallFeed", "eventsFeed", "searchUsers"],
    "publicaciones.crear-post": ["wallFeed", "getImage"],
    "publicaciones.historias-vivos": ["wallFeed"],
    "publicaciones.busqueda-global": ["searchEvents", "searchUsers", "wallFeed"],
    "publicaciones.reportar": ["wallFeed"],
    "usuarios.perfil-publico": ["getUser", "profileImages", "searchUsers", "wallFeed"],
    "usuarios.editar-perfil": ["updateUser", "profileImages", "profileImagesUpload"],
    "usuarios.autenticacion": ["login", "googleOAuth", "facebookOAuth", "createUser", "generateOtp"],
    "usuarios.kyc.certificacion": ["getUser", "updateUser"],
    "eventos.crear.wizard": ["createEvent", "publishEvent", "getImage", "eventTypes"],
    "eventos.estadisticas": ["getUserEvents", "getUserStats", "eventCalifications"],
    "eventos.asistente-ia": ["aiAssistant"],
    "tickets.compra.flow": ["userTickets", "wompiBase"],
    "tickets.mis-compras": ["userTickets", "canRequestRefund", "processRefund"],
    "tickets.transferir.flow": ["userTickets"],
    "tickets.reembolsar.flow": ["canRequestRefund", "processRefund"],
    "chat.privado": ["chatRestBase"],
    "notificaciones.sistema": ["notificationsByUser", "updateNotification", "triggerNotification"],
    "servicios.crear.wizard": ["servicesBase"],
    "servicios.reservar.booking": ["servicesBase"],
    "lugares.crear.wizard": ["createVenue"],
    "lugares.detalle-lugar": ["createVenue"],
    "lugares.mapa-explorador": ["searchEvents", "createVenue"],
    "invitados.gestion": ["guestsBase", "userInvitations"],
    "pagos.checkout-seguro": ["wompiBase"],
    "pagos.suscripcion-pro": ["subscriptionsBase"],
    "bancarios.banking-form": ["bankDataByUser", "createBankData", "setDefaultBankData"],
    "admin.panel": ["adminBase"],
    "acceso.escaneo-qr": ["userTickets"],
}

# Prefijos URI (segmento tras api-dev.doeventsapp.com) por dominio DSF
DOMAIN_URI_PREFIXES: dict[str, list[str]] = {
    "publicaciones": ["wall"],
    "eventos": ["events", "events-feed", "event-types"],
    "usuarios": ["users", "login", "auth"],
    "tickets": ["orders", "events"],
    "chat": ["chats"],
    "notificaciones": ["notifications"],
    "servicios": ["services"],
    "lugares": ["venues"],
    "pagos": ["checkouts", "subscriptions"],
    "bancarios": ["bank"],
    "admin": ["backoffice"],
    "invitados": ["guests"],
    "acceso": ["staff-access"],
    "persistencia": [],
    "infra": [],
}

ALL_WEB_KEYS = [
    "login", "googleOAuth", "facebookOAuth", "appleOAuth", "createUser", "updateUser",
    "getUser", "generateOtp", "eventsFeed", "getUserEvents", "getEvent", "createEvent",
    "publishEvent", "searchEvents", "eventLike", "wallFeed", "getImage", "userTickets",
    "notificationsByUser", "searchUsers", "createVenue", "servicesBase", "wompiBase",
    "subscriptionsBase", "adminBase", "aiAssistant", "bankDataByUser", "guestsBase",
    "chatRestBase", "canRequestRefund", "processRefund", "triggerNotification",
]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_rules(lovable_root: Path) -> dict[str, dict[str, Any]]:
    """ruleId -> {webKeys, uriPrefixes, domain}"""
    out: dict[str, dict[str, Any]] = {}
    rules_dir = lovable_root / "reglasActuacion"
    if not rules_dir.is_dir():
        return out
    for yml in rules_dir.rglob("*.yml"):
        data = _load_yaml(yml)
        rule_id = str(data.get("id", "")).strip()
        if not rule_id:
            continue
        domain = str(data.get("domain", rule_id.split(".")[0]))
        webkeys: set[str] = set(RULE_WEBKEYS.get(rule_id, []))
        webkeys.update(DOMAIN_WEBKEYS_FALLBACK(domain))
        emp = data.get("empalme") or {}
        for trigger in emp.get("cursorTriggers") or []:
            tl = str(trigger).lower()
            for wk in ALL_WEB_KEYS:
                if wk.lower() in tl.replace(" ", "").replace("-", ""):
                    webkeys.add(wk)
        bc = emp.get("backendContract") or data.get("backendContract") or {}
        for wk in bc.get("webKeys") or []:
            webkeys.add(str(wk))
        ep_uri = str(bc.get("uri") or bc.get("endpoint") or "").strip()
        uri_prefixes = list(DOMAIN_URI_PREFIXES.get(domain, []))
        if ep_uri:
            m = re.match(r"https?://[^/]+/([^/]+)", ep_uri)
            if m:
                uri_prefixes.append(m.group(1))
        out[rule_id] = {
            "domain": domain,
            "webKeys": sorted(webkeys),
            "uriPrefixes": sorted(set(uri_prefixes)),
        }
    return out


def DOMAIN_WEBKEYS_FALLBACK(domain: str) -> list[str]:
    return {
        "publicaciones": ["wallFeed", "eventsFeed"],
        "eventos": ["getUserEvents", "createEvent", "searchEvents"],
        "usuarios": ["getUser", "updateUser", "profileImages"],
        "tickets": ["userTickets"],
        "chat": ["chatRestBase"],
        "notificaciones": ["notificationsByUser"],
        "servicios": ["servicesBase"],
        "lugares": ["createVenue"],
        "pagos": ["wompiBase", "subscriptionsBase"],
        "bancarios": ["bankDataByUser"],
        "admin": ["adminBase"],
        "invitados": ["guestsBase"],
        "acceso": ["userTickets"],
    }.get(domain, [])


def link_consumers(
    endpoints: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    api_base: str,
) -> tuple[list[dict[str, Any]], int]:
    """Añade ruleIds a consumers[] en cada endpoint. Devuelve (endpoints, links_count)."""
    base = api_base.rstrip("/")
    links = 0
    for ep in endpoints:
        consumers: set[str] = set(ep.get("consumers") or [])
        uri = str(ep.get("uri", ""))
        webkey = str(ep.get("webKey", ""))
        rel = uri.replace(base, "").lstrip("/")
        first_seg = rel.split("/")[0] if rel else ""

        for rule_id, meta in rules.items():
            if webkey and webkey in meta["webKeys"]:
                if rule_id not in consumers:
                    consumers.add(rule_id)
                    links += 1
            elif first_seg and first_seg in meta["uriPrefixes"]:
                if rule_id not in consumers:
                    consumers.add(rule_id)
                    links += 1
        ep["consumers"] = sorted(consumers)
    return endpoints, links


def apply_to_file(lovable_root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    path = lovable_root / "contratosBackend" / "endpoints.yml"
    data = _load_yaml(path)
    endpoints = list(data.get("endpoints") or [])
    api_base = str(data.get("apiBase", "https://api-dev.doeventsapp.com"))
    rules = load_rules(lovable_root)
    endpoints, links = link_consumers(endpoints, rules, api_base)
    with_consumers = sum(1 for e in endpoints if e.get("consumers"))
    summary = {
        "endpointCount": len(endpoints),
        "ruleCount": len(rules),
        "linksAdded": links,
        "endpointsWithConsumers": with_consumers,
    }
    if not dry_run and yaml is not None:
        data["endpoints"] = endpoints
        data["consumersLinkedAt"] = __import__("datetime").date.today().isoformat()
        data["consumersLinkSummary"] = summary
        text = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        path.write_text(
            "# DSF — contratosBackend/endpoints.yml (auto-generado + consumers)\n"
            "# Fuente: DoEventsBack + reglasActuacion\n\n" + text,
            encoding="utf-8",
        )
    return summary


def main() -> int:
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Enlazar consumers reglas DSF → endpoints.yml")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = apply_to_file(Path(args.lovable_dir).resolve(), dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
