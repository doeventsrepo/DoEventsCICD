#!/usr/bin/env python3
"""
BSF — Detecta cambios en Frontend/Lovable que requieren ajuste en Backend.

Analiza:
- Manifiesto de cambios DSF (changedFiles)
- Diff WEB (packages/shared, pages, lovable-bridge)
- Señales: formularios, validaciones, rutas, campos nuevos, llamadas API
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import BACKEND_HINTS, load_manifest, norm_path, save_json
from agent_base import artifacts_dir, cicd_root, gh_output, write_report

try:
    from backend_sync_log import append_log
except ImportError:
    def append_log(*_a, **_k):  # type: ignore
        return Path()


def load_registry() -> dict[str, Any]:
    path = cicd_root() / "dsf" / "backend-registry.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def classify_file(path: str, registry: dict[str, Any]) -> list[str]:
    """Devuelve dominios backend afectados."""
    p = norm_path(path).lower()
    domains: list[str] = []
    for domain_id, meta in (registry.get("domains") or {}).items():
        for hint in meta.get("lovableHints") or []:
            if hint.lower() in p:
                domains.append(domain_id)
                break
        for consumer in meta.get("webConsumers") or []:
            c = norm_path(consumer).lower().rstrip("/")
            if c and (p == c or p.startswith(c) or c in p):
                domains.append(domain_id)
                break
    return list(dict.fromkeys(domains))


def scan_content(path: Path, signals: dict[str, list[str]]) -> dict[str, int]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    counts: dict[str, int] = {}
    for signal_type, patterns in signals.items():
        n = 0
        for pat in patterns:
            n += len(re.findall(re.escape(pat), text, re.I))
        if BACKEND_HINTS.search(text):
            n += 1
        if n:
            counts[signal_type] = n
    return counts


def extract_new_fields(text: str) -> list[str]:
    """Heurística: campos nuevos en formularios TS/TSX."""
    fields: set[str] = set()
    for m in re.finditer(r"(?:name|id)=['\"]([a-zA-Z_][\w]*)['\"]", text):
        fields.add(m.group(1))
    for m in re.finditer(r"(\w+)\s*:\s*(?:string|number|boolean)\s*[,;}]", text):
        if m.group(1) not in ("id", "type", "key", "className", "style"):
            fields.add(m.group(1))
    return sorted(fields)[:40]


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF detect frontend-backend delta")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    registry = load_registry()
    signals = registry.get("changeSignals") or {}

    changed = manifest.get("changedFiles") or []
    items: list[dict[str, Any]] = []

    paths_to_scan: list[tuple[str, Path]] = []
    for entry in changed:
        rel = norm_path(str(entry.get("path", "")))
        if not rel:
            continue
        for root_name, root in (("lovable", lovable), ("web", web)):
            candidate = root / rel if root_name == "lovable" else _web_path(web, rel)
            if candidate and candidate.is_file():
                paths_to_scan.append((rel, candidate))

    # Siempre escanear impacto-backend y shared si existen cambios WEB
    impacto = web / "ReglasAgente" / "impacto-backend.md"
    if impacto.is_file():
        paths_to_scan.append(("ReglasAgente/impacto-backend.md", impacto))

    seen: set[str] = set()
    for rel, path in paths_to_scan:
        if rel in seen:
            continue
        seen.add(rel)
        domains = classify_file(rel, registry)
        text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
        signal_counts = scan_content(path, signals)
        new_fields = extract_new_fields(text) if signal_counts.get("formField") or signal_counts.get("newForm") else []
        requires_backend = bool(domains) or bool(signal_counts) or "BACKEND_REQUIRED" in text

        item = {
            "path": rel,
            "domains": domains,
            "signalCounts": signal_counts,
            "newFields": new_fields,
            "requiresBackend": requires_backend,
            "changeTypes": _infer_change_types(signal_counts, new_fields),
            "lambdaTargets": [
                {
                    "domain": d,
                    "lambdaDir": (registry.get("domains") or {}).get(d, {}).get("lambdaDir"),
                    "apiPrefix": (registry.get("domains") or {}).get(d, {}).get("apiPrefix"),
                }
                for d in domains
            ],
        }
        items.append(item)
        if requires_backend:
            append_log(
                "delta_detected",
                level="info",
                message=f"Cambio requiere backend: {rel}",
                domain=domains[0] if domains else None,
                metadata={"signals": signal_counts, "fields": new_fields},
                run_id=args.run_id,
            )

    domains_union = sorted({d for it in items for d in it["domains"]})
    lambda_dirs = sorted({
        t["lambdaDir"]
        for it in items
        for t in it["lambdaTargets"]
        if t.get("lambdaDir")
    })

    result = {
        "runId": args.run_id,
        "itemsCount": len(items),
        "requiresBackendCount": sum(1 for i in items if i["requiresBackend"]),
        "domainsAffected": domains_union,
        "lambdaDirsToDeploy": lambda_dirs,
        "items": items,
    }

    out = artifacts_dir(args.run_id) / f"backend-delta-{args.run_id}.json"
    save_json(out, result)
    write_report(f"backend-delta-{args.run_id}.json", result, args.run_id)
    gh_output("backend_delta_requires", str(result["requiresBackendCount"] > 0).lower())
    gh_output("backend_domains", ",".join(domains_union))
    print(json.dumps({"ok": True, "requiresBackend": result["requiresBackendCount"]}, indent=2))
    return 0


def _web_path(web: Path, rel: str) -> Path | None:
    candidates = [
        web / rel,
        web / "packages/shell/src/lovable" / rel.replace("src/components/", ""),
        web / rel.replace("src/", "packages/shell/src/lovable/"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _infer_change_types(signals: dict[str, int], fields: list[str]) -> list[str]:
    types: list[str] = []
    if signals.get("formField") or signals.get("newForm") or fields:
        types.append("form_fields")
    if signals.get("apiCall"):
        types.append("api_contract")
    if signals.get("routing"):
        types.append("routing")
    if signals.get("businessLogic"):
        types.append("business_logic")
    return types or ["visual_only"]


if __name__ == "__main__":
    sys.exit(main())
