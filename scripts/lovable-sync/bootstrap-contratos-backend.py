#!/usr/bin/env python3
"""
Bootstrap contratosBackend/endpoints.yml desde DoEventsBack (serverless.dev.yml)
y cruce con DoEventsWEB/config/environments/index.ts (devaws).

Genera URIs completas DEV: https://api-dev.doeventsapp.com/{prefix}/{path}
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

DEFAULT_API_BASE = "https://api-dev.doeventsapp.com"
DEFAULT_WS_BASE = "wss://ws-dev.doeventsapp.com"

# service (campo serverless) -> prefijo API Gateway en api-dev.doeventsapp.com
SERVICE_API_PREFIX: dict[str, str] = {
    "aws-lambda-login": "login",
    "aws-lambda-manageusers": "users",
    "aws-lambda-generateotp": "auth",
    "aws-lambda-eventsFeed": "events-feed",
    "aws-lambda-manageevent": "events",
    "aws-lambda-EventType": "event-types",
    "aws-lambda-wall-social-media": "wall",
    "aws-lambda-imagenes": "images",
    "aws-lambda-orders-manageTickets": "orders",
    "notifications": "notifications",
    "aws-lambda-venues": "venues",
    "aws-lambda-DatosBancarios": "bank",
    "aws-lambda-Bancos": "bank",
    "aws-lambda-guests": "guests",
    "aws-lambda-services": "services",
    "wompi-checkouts": "checkouts",
    "aws-lambda-subscriptions": "subscriptions",
    "aws-lambda-backoffice": "backoffice",
    "chat-room-events": "chats",
    "doevents-agentes-ia": "ai",
    "staff-access": "staff-access",
    "aws-lambda-eventsLifecycleManager": "events-lifecycle",
}

AUTH_HINTS = re.compile(r"authorizer|Authorization|Bearer|private:\s*true", re.I)


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip("/")).strip("-").lower()
    return s[:80] or "root"


def parse_web_endpoint_map(web_index: Path, base_url: str) -> dict[str, str]:
    """webKey -> URI completa (devaws)."""
    if not web_index.is_file():
        return {}
    text = web_index.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    for key, rel in re.findall(r"(\w+):\s*`?\$\{baseUrl\}([^`\"']+)`?", text):
        rel = rel.split("${")[0].strip().rstrip("/")
        if rel:
            out[key] = f"{base_url.rstrip('/')}{rel}"
    chat_rest = re.search(r"DEVAWS_CHAT_REST\s*=\s*['\"]([^'\"]+)['\"]", text)
    if chat_rest:
        out["chatRestBase"] = chat_rest.group(1).rstrip("/")
    return out


def invert_web_map(web_map: dict[str, str]) -> dict[str, str]:
    return {uri.rstrip("/"): key for key, uri in web_map.items()}


def load_serverless_file(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception as exc:
        print(f"AVISO: no se pudo leer {path}: {exc}", file=sys.stderr)
        return {}


def extract_http_events(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(functionName, method, path)"""
    out: list[tuple[str, str, str]] = []
    functions = data.get("functions") or {}
    if not isinstance(functions, dict):
        return out
    for fn_name, fn_cfg in functions.items():
        if not isinstance(fn_cfg, dict):
            continue
        for ev in fn_cfg.get("events") or []:
            if not isinstance(ev, dict):
                continue
            if "http" in ev:
                http = ev["http"] or {}
                method = str(http.get("method", "get")).upper()
                path = str(http.get("path", "")).strip()
                if path:
                    out.append((fn_name, method, path))
            elif "httpApi" in ev:
                http = ev["httpApi"] or {}
                method = str(http.get("method", "get")).upper()
                path = str(http.get("path", "")).strip()
                if path:
                    out.append((fn_name, method, path))
    return out


def build_uri(base: str, prefix: str, raw_path: str) -> tuple[str, str]:
    """Devuelve (uri_completa, path_relativo_desde_dominio)."""
    p = raw_path.lstrip("/")
    rel = f"/{prefix}/{p}" if prefix else f"/{p}"
    rel = re.sub(r"/+", "/", rel)
    uri = urljoin(base.rstrip("/") + "/", rel.lstrip("/"))
    return uri.rstrip("/"), rel


def guess_auth(fn_name: str, raw_path: str, fn_block: dict) -> bool:
    blob = yaml.dump(fn_block, allow_unicode=True)
    if AUTH_HINTS.search(blob):
        return True
    public_hints = ("login", "oauth", "callback", "doc", "swagger", "health")
    low = f"{fn_name} {raw_path}".lower()
    if any(h in low for h in public_hints):
        return False
    return True


def collect_serverless_endpoints(back_root: Path, api_base: str) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    items: list[dict[str, Any]] = []

    dev_files = sorted(back_root.glob("**/serverless.dev.yml"))
    if not dev_files:
        dev_files = sorted(back_root.glob("**/serverless.yml"))

    for sls_path in dev_files:
        data = load_serverless_file(sls_path)
        service = str(data.get("service") or sls_path.parent.name)
        prefix = SERVICE_API_PREFIX.get(service)
        if prefix is None:
            print(f"AVISO: sin prefijo API para service={service} ({sls_path.parent.name})", file=sys.stderr)
            prefix = sls_path.parent.name.replace("aws-lambda-", "").replace("aws-lamda-", "")

        functions = data.get("functions") or {}
        for fn_name, method, raw_path in extract_http_events(data):
            key = (service, method, raw_path)
            if key in seen:
                continue
            seen.add(key)
            uri, rel_path = build_uri(api_base, prefix, raw_path)
            fn_block = functions.get(fn_name, {}) if isinstance(functions, dict) else {}
            endpoint_id = f"{prefix}.{slug(fn_name)}.{slug(raw_path)}"
            items.append({
                "id": endpoint_id,
                "method": method,
                "uri": uri,
                "path": rel_path,
                "service": service,
                "serverlessFunction": fn_name,
                "serverlessPath": raw_path,
                "sourceRepo": sls_path.parent.name,
                "environment": "dev",
                "apiBase": api_base,
                "implementedInDoEventsBack": True,
                "authRequired": guess_auth(fn_name, raw_path, fn_block if isinstance(fn_block, dict) else {}),
                "consumers": [],
                "webKey": "",
            })
    return items


def attach_web_keys(endpoints: list[dict[str, Any]], web_uri_to_key: dict[str, str]) -> None:
    for ep in endpoints:
        uri = ep.get("uri", "").rstrip("/")
        ep["webKey"] = web_uri_to_key.get(uri, "")


def write_endpoints_yml(
    out_path: Path,
    endpoints: list[dict[str, Any]],
    *,
    api_base: str,
    dry_run: bool,
) -> None:
    payload = {
        "id": "backend.contratos",
        "version": "1.2",
        "generatedBy": "bootstrap-contratos-backend.py",
        "lastUpdated": date.today().isoformat(),
        "canonicalEnvironment": "dev",
        "apiBase": api_base,
        "websocketBase": DEFAULT_WS_BASE,
        "note": (
            "Catálogo generado desde DoEventsBack/serverless.dev.yml + DoEventsWEB devaws. "
            "URIs completas DEV. Regenerar con bootstrap-contratos-backend.py tras cambios en Back."
        ),
        "endpointCount": len(endpoints),
        "endpoints": sorted(endpoints, key=lambda e: (e.get("uri", ""), e.get("method", ""))),
    }
    text = yaml.dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)
    header = (
        "# DSF — contratosBackend/endpoints.yml (auto-generado)\n"
        "# Fuente: DoEventsBack serverless.dev.yml + DoEventsWEB config/environments/index.ts\n\n"
    )
    if dry_run:
        print(f"[dry-run] escribiria {len(endpoints)} endpoints en {out_path}")
        print(yaml.dump({"endpointCount": len(endpoints), "sample": endpoints[:3]}, allow_unicode=True))
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header + text, encoding="utf-8")
    print(f"OK: {len(endpoints)} endpoints -> {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap contratosBackend/endpoints.yml")
    parser.add_argument("--back-dir", default="", help="Raíz DoEventsBack")
    parser.add_argument("--web-dir", default="", help="Raíz DoEventsWEB")
    parser.add_argument("--lovable-dir", required=True, help="Raíz discover-joyful-feed (destino endpoints.yml)")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    monorepo = root.parent
    back_root = Path(args.back_dir or monorepo / "DoEventsBack").resolve()
    web_root = Path(args.web_dir or monorepo / "DoEventsWEB").resolve()
    lovable_root = Path(args.lovable_dir).resolve()
    out_path = lovable_root / "contratosBackend" / "endpoints.yml"
    api_base = args.api_base.rstrip("/")

    if not back_root.is_dir():
        print(f"ERROR: DoEventsBack no encontrado: {back_root}", file=sys.stderr)
        return 1

    web_map = parse_web_endpoint_map(web_root / "config" / "environments" / "index.ts", api_base)
    web_uri_to_key = invert_web_map(web_map)

    endpoints = collect_serverless_endpoints(back_root, api_base)
    attach_web_keys(endpoints, web_uri_to_key)

    write_endpoints_yml(out_path, endpoints, api_base=api_base, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
