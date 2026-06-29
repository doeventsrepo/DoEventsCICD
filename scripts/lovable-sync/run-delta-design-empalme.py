#!/usr/bin/env python3
"""Aplica diff diseño Lovable sobre WEB preservando líneas bridge/API."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from design_tokens import load_design_tokens
from empalme_delta import BRIDGE_IMPORT_MARKERS, apply_lovable_delta, check_regression
from empalme_engine import transform_lovable_source
from port_map_utils import load_port_map, map_lovable_to_web

SKIP_SUFFIXES = (
    "/components/admin/",
    "/components/feed/MapView.tsx",
    "/contexts/KycContext.tsx",
    "/hooks/useGuests.ts",
    "/pages/",
)

BACKEND_LINE = re.compile(
    r"@doevents/shared|lovable-bridge|api-dev\.doeventsapp|"
    r"\b(searchUsers|fetchSocialFeed|reportPublication|getPreferences|fetchEventTypes|"
    r"fetchFollowers|followUser|searchEvents|useToast|useSelector|RootState|"
    r"resolveUserLocation|resolveManualUserLocation|loadGoogleMapsScript|"
    r"getStoredUserLocation|mapItems|MapViewProps|MapItemData)\b|"
    r"handleDeviceLocation|handlePlaceSearch|onSearchKeyDown|"
    r"await\s+fetch\b"
)


def should_skip(lovable_rel: str) -> str | None:
    norm = lovable_rel.replace("\\", "/")
    for suffix in SKIP_SUFFIXES:
        if suffix.endswith("/") and suffix in norm:
            return suffix
        if norm.endswith(suffix):
            return suffix
    return None


def strip_backend_lines(text: str) -> str:
    """Aproxima WEB → baseline Lovable quitando cableado backend."""
    out: list[str] = []
    skip_depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if skip_depth > 0:
            skip_depth += line.count("{") - line.count("}")
            if skip_depth <= 0:
                skip_depth = 0
            continue
        if stripped.startswith("import ") and any(m in line for m in BRIDGE_IMPORT_MARKERS):
            continue
        if BACKEND_LINE.search(line):
            if "{" in line and "}" not in line:
                skip_depth = 1
            continue
        out.append(line)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Delta diseño WEB←Lovable con anti-regresión")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="empalme-delta-design.json")
    parser.add_argument("--only", default="", help="CSV lovablePath a procesar (ignora skip parcial)")
    args = parser.parse_args()

    only_set = {p.strip() for p in args.only.split(",") if p.strip()}

    lovable_root = Path(args.lovable_dir).resolve()
    web_root = Path(args.web_dir).resolve()
    mapping = load_port_map(Path(args.port_map).resolve())
    comparison = json.loads(Path(args.comparison).read_text(encoding="utf-8"))
    tokens = load_design_tokens(lovable_root)

    targets = comparison.get("lowSimilarity") or []
    applied: list[dict] = []
    skipped: list[dict] = []

    for entry in targets:
        lovable_rel = entry.get("lovablePath", "")
        if not lovable_rel:
            continue
        if only_set and lovable_rel not in only_set:
            continue
        skip = should_skip(lovable_rel)
        if skip and lovable_rel not in only_set:
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
        lovable_raw = lovable_path.read_text(encoding="utf-8", errors="replace")
        lovable_new = transform_lovable_source(lovable_raw, tokens=tokens, lovable_root=lovable_root)
        lovable_old = strip_backend_lines(web_original)

        result = apply_lovable_delta(
            web_original=web_original,
            lovable_old=lovable_old,
            lovable_new=lovable_new,
        )
        ok, violations = check_regression(web_original, result.web_text, lovable_old, lovable_new)
        if not ok:
            skipped.append({
                "lovablePath": lovable_rel,
                "reason": "regression",
                "violations": violations,
            })
            continue
        if result.applied_ops == 0 or result.web_text.strip() == web_original.strip():
            skipped.append({"lovablePath": lovable_rel, "reason": "sin_ops", "missed": result.missed[:3]})
            continue

        if not args.dry_run:
            web_path.write_text(result.web_text, encoding="utf-8")
        applied.append({
            "lovablePath": lovable_rel,
            "webPath": web_rel,
            "ops": result.applied_ops,
            "similarityPercent": entry.get("similarityPercent"),
        })

    report = {"applied": applied, "skipped": skipped}
    Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"applied": len(applied), "skipped": len(skipped)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
