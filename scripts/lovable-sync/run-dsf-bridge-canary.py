#!/usr/bin/env python3
"""Canario DSF — valida componentes con bridge WEB listos para empalme delta-only."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from empalme_engine import BRIDGE_MARKERS, classify_tier
from port_map_utils import load_port_map, map_lovable_to_web


def load_canary(cicd_root: Path) -> list[dict]:
    path = cicd_root / "dsf" / "canary-bridge-components.yml"
    if not path.is_file() or yaml is None:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("components") or [])


def resolve_web_component(lovable_path: str, web_root: Path, port_map: dict) -> tuple[Path, str]:
    """Resuelve archivo WEB empalado; prioriza packages/shell/src/lovable/ sobre página contenedora."""
    lp = lovable_path.replace("\\", "/").lstrip("./")
    component_rel = f"packages/shell/src/lovable/{lp.removeprefix('src/')}"
    component_full = web_root / component_rel
    if component_full.is_file():
        return component_full, component_rel
    web_rel = map_lovable_to_web(lp, port_map) or ""
    if web_rel:
        full = web_root / web_rel
        if full.is_file():
            return full, web_rel
    return Path(), ""


def check_component(
    *,
    item: dict,
    lovable_root: Path,
    web_root: Path,
    port_map: dict,
) -> dict:
    lp = item.get("lovablePath", "")
    web_path, web_rel = resolve_web_component(lp, web_root, port_map)
    markers = item.get("bridgeMarkers") or ["@doevents/shared"]

    result = {
        "lovablePath": lp,
        "ruleId": item.get("ruleId", ""),
        "webPath": web_rel,
        "ok": True,
        "checks": {},
    }

    if not web_path.is_file():
        result["ok"] = False
        result["checks"]["webExists"] = False
        return result
    result["checks"]["webExists"] = True

    web_src = web_path.read_text(encoding="utf-8", errors="replace")
    lovable_path = lovable_root / lp
    lovable_src = lovable_path.read_text(encoding="utf-8", errors="replace") if lovable_path.is_file() else ""

    missing_markers = [m for m in markers if m not in web_src]
    result["checks"]["bridgeMarkers"] = {
        "required": markers,
        "missing": missing_markers,
        "ok": len(missing_markers) == 0,
    }
    if missing_markers:
        result["ok"] = False

    has_bridge = bool(BRIDGE_MARKERS.search(web_src))
    result["checks"]["bridgePattern"] = has_bridge

    tier, reason = classify_tier(
        lovable_path=lp,
        web_path=web_rel,
        similarity=80.0,
        status="minor_drift",
        lovable_src=lovable_src,
        web_src=web_src,
        compare_mode="",
        python_max_sim=85.0,
        force_paths={lp},
        force_diff_apply=True,
        lovable_root=lovable_root,
    )
    result["checks"]["empalmeTier"] = tier
    result["checks"]["empalmeReason"] = reason
    result["checks"]["deltaReady"] = tier == "python" and "delta" in reason
    # Cursor por regla YAML es válido en componentes complejos (MapView, StoryViewer)
    if tier == "cursor" and "regla_yaml_cursor" in reason:
        result["checks"]["tierNote"] = "cursor_esperado_por_regla"

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF bridge canary")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--port-map", default="")
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    web = Path(args.web_dir).resolve()
    cicd = Path(args.cicd_dir).resolve()
    port_map_path = Path(args.port_map) if args.port_map else web / ".lovable-port-map.json"
    port_map = load_port_map(port_map_path)

    items = load_canary(cicd)
    results = [
        check_component(item=item, lovable_root=lovable, web_root=web, port_map=port_map)
        for item in items
    ]
    passed = sum(1 for r in results if r.get("ok"))
    payload = {
        "runId": args.run_id,
        "canaryCount": len(results),
        "passedCount": passed,
        "failedCount": len(results) - passed,
        "allPassed": passed == len(results) and len(results) > 0,
        "results": results,
    }

    out = Path(args.out) if args.out else cicd / "artifacts" / f"dsf-bridge-canary-{args.run_id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"allPassed": payload["allPassed"], "passed": passed, "total": len(results)}, indent=2))
    return 0 if payload["allPassed"] else 1


if __name__ == "__main__":
    sys.exit(main())
