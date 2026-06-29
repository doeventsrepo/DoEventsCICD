#!/usr/bin/env python3
"""Empalme híbrido: diseño Lovable + preservar imports/exports bridge del WEB."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from design_tokens import load_design_tokens
from empalme_engine import (
    preserve_bridge_imports,
    preserve_lovable_asset_imports,
    preserve_web_exports,
    transform_lovable_source,
)
from port_map_utils import load_port_map, map_lovable_to_web

# Baja similitud esperada — no sobreescribir stubs/delegación/cableado crítico
HYBRID_SKIP_SUFFIXES = (
    "/components/admin/",
    "/components/feed/MapView.tsx",
    "/contexts/KycContext.tsx",
    "/hooks/useGuests.ts",
    "/pages/",
)

SHARED_USAGE = re.compile(
    r"\b(searchUsers|fetchSocialFeed|reportPublication|getPreferences|fetchEventTypes|"
    r"@doevents/shared|lovable-bridge)\b"
)


def should_skip(lovable_rel: str) -> str | None:
    norm = lovable_rel.replace("\\", "/")
    for suffix in HYBRID_SKIP_SUFFIXES:
        if suffix.endswith("/") and suffix in norm:
            return suffix
        if norm.endswith(suffix):
            return suffix
    return None


def shared_usage_count(text: str) -> int:
    return len(SHARED_USAGE.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(description="Empalme híbrido diseño (31 archivos pendientes)")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="empalme-hybrid-design.json")
    args = parser.parse_args()

    lovable_root = Path(args.lovable_dir).resolve()
    web_root = Path(args.web_dir).resolve()
    mapping = load_port_map(Path(args.port_map).resolve())
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    tokens = load_design_tokens(lovable_root)

    targets = comparison.get("lowSimilarity") or []
    applied: list[dict] = []
    skipped: list[dict] = []
    guarded: list[dict] = []

    for entry in targets:
        lovable_rel = entry.get("lovablePath", "")
        if not lovable_rel:
            continue
        skip = should_skip(lovable_rel)
        if skip:
            skipped.append({"lovablePath": lovable_rel, "reason": f"skip:{skip}"})
            continue

        web_rel = map_lovable_to_web(lovable_rel, mapping)
        if not web_rel:
            skipped.append({"lovablePath": lovable_rel, "reason": "unmapped"})
            continue

        lovable_path = lovable_root / lovable_rel
        web_path = web_root / web_rel
        if not lovable_path.is_file() or not web_path.is_file():
            skipped.append({"lovablePath": lovable_rel, "reason": "missing_file"})
            continue

        web_original = web_path.read_text(encoding="utf-8", errors="replace")
        before_shared = shared_usage_count(web_original)
        lovable_raw = lovable_path.read_text(encoding="utf-8", errors="replace")
        transformed = transform_lovable_source(lovable_raw, tokens=tokens, lovable_root=lovable_root)
        transformed = preserve_bridge_imports(web_original, transformed)
        transformed = preserve_lovable_asset_imports(
            lovable_raw, transformed, tokens=tokens, lovable_root=lovable_root,
        )
        transformed = preserve_web_exports(web_original, transformed)

        after_shared = shared_usage_count(transformed)
        if before_shared > 0 and after_shared < before_shared:
            skipped.append({
                "lovablePath": lovable_rel,
                "webPath": web_rel,
                "reason": f"shared_guard:{before_shared}->{after_shared}",
            })
            guarded.append({"lovablePath": lovable_rel, "webPath": web_rel})
            continue

        if transformed.strip() == web_original.strip():
            skipped.append({"lovablePath": lovable_rel, "reason": "sin_cambios"})
            continue

        if not args.dry_run:
            web_path.write_text(transformed, encoding="utf-8")
        applied.append({
            "lovablePath": lovable_rel,
            "webPath": web_rel,
            "similarityPercent": entry.get("similarityPercent"),
        })

    report = {"applied": applied, "skipped": skipped, "guarded": guarded}
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "applied": len(applied),
        "skipped": len(skipped),
        "guarded": len(guarded),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
