#!/usr/bin/env python3
"""Empalme manual Lovable→WEB: full sync forzado (sin Cursor API, sin gap loop)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from design_tokens import load_design_tokens
from empalme_engine import (
    EmpalmeItem,
    preserve_bridge_imports,
    preserve_lovable_asset_imports,
    preserve_web_exports,
    transform_lovable_source,
)
from port_map_utils import is_excluded, load_port_map, load_port_map_data, map_lovable_to_web

SKIP_SUFFIXES = (
    "/contexts/KycContext.tsx",
    "/contexts/PrivacyContext.tsx",
    "/contexts/CompanyContext.tsx",
    "/contexts/NotificationsContext.tsx",
    "/components/feed/MapView.tsx",
    "/components/admin/",
    "/components/auth/",
)


def should_skip_manual(lovable_rel: str, web_src: str) -> str | None:
    norm = lovable_rel.replace("\\", "/")
    for suffix in SKIP_SUFFIXES:
        if suffix.endswith("/") and suffix in norm:
            return f"skip_path:{suffix}"
        if norm.endswith(suffix):
            return f"skip_path:{suffix}"
    if "lovable-bridge" in web_src or "@doevents/shared" in web_src:
        if "/contexts/" in norm:
            return "skip_bridge_context"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Empalme manual full-sync Lovable→WEB")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--max-sim", type=float, default=98.0, help="Solo archivos bajo este %")
    parser.add_argument("--max-items", type=int, default=80)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="empalme-manual-full.json")
    parser.add_argument("--run-id", default="manual-full")
    args = parser.parse_args()

    lovable_root = Path(args.lovable_dir).resolve()
    web_root = Path(args.web_dir).resolve()
    port_map = Path(args.port_map).resolve()
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    mapping = load_port_map(port_map)
    port_data = load_port_map_data(port_map)
    tokens = load_design_tokens(lovable_root)

    applied: list[dict] = []
    skipped: list[dict] = []
    errors: list[dict] = []

    files = comparison.get("files") or comparison.get("lowSimilarity") or []
    candidates = [
        f for f in files
        if float(f.get("similarityPercent", 100)) < args.max_sim
        and f.get("status") != "aligned"
    ]
    candidates.sort(key=lambda x: float(x.get("similarityPercent", 0)))

    for entry in candidates[: args.max_items]:
        lovable_rel = entry.get("lovablePath", "")
        if not lovable_rel or is_excluded(lovable_rel, port_data):
            continue
        web_rel = map_lovable_to_web(lovable_rel, mapping)
        if not web_rel:
            skipped.append({"lovablePath": lovable_rel, "reason": "unmapped"})
            continue

        lovable_path = lovable_root / lovable_rel
        web_path = web_root / web_rel
        if not lovable_path.is_file():
            skipped.append({"lovablePath": lovable_rel, "reason": "missing_lovable"})
            continue

        web_original = web_path.read_text(encoding="utf-8", errors="replace") if web_path.is_file() else ""
        skip_reason = should_skip_manual(lovable_rel, web_original)
        if skip_reason:
            skipped.append({"lovablePath": lovable_rel, "webPath": web_rel, "reason": skip_reason})
            continue

        lovable_raw = lovable_path.read_text(encoding="utf-8", errors="replace")
        transformed = transform_lovable_source(lovable_raw, tokens=tokens, lovable_root=lovable_root)
        if web_original:
            transformed = preserve_bridge_imports(web_original, transformed)
            transformed = preserve_lovable_asset_imports(
                lovable_raw, transformed, tokens=tokens, lovable_root=lovable_root,
            )
            transformed = preserve_web_exports(web_original, transformed)
            if transformed.strip() == web_original.strip():
                skipped.append({"lovablePath": lovable_rel, "webPath": web_rel, "reason": "sin_cambios"})
                continue

        try:
            if not args.dry_run:
                web_path.parent.mkdir(parents=True, exist_ok=True)
                web_path.write_text(transformed, encoding="utf-8")
            applied.append({
                "lovablePath": lovable_rel,
                "webPath": web_rel,
                "similarityPercent": entry.get("similarityPercent"),
                "dryRun": args.dry_run,
            })
        except OSError as exc:
            errors.append({"lovablePath": lovable_rel, "error": str(exc)})

    payload = {
        "runId": args.run_id,
        "dryRun": args.dry_run,
        "appliedCount": len(applied),
        "skippedCount": len(skipped),
        "errorCount": len(errors),
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"applied": len(applied), "skipped": len(skipped), "errors": len(errors)}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
