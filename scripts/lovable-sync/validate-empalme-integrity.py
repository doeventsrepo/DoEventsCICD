#!/usr/bin/env python3
"""Gate post-empalme: integridad bridge pages y ausencia de mocks en runtime WEB."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD_ROOT))

from dsf.reliability import bridge_page_for, gate, load_reliability  # noqa: E402
from port_map_utils import load_port_map, map_lovable_to_web  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF empalme integrity gate")
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--port-map", default="")
    parser.add_argument("--app-id", default="doevents")
    parser.add_argument("--blocking", default="true")
    args = parser.parse_args()

    web = Path(args.web_dir).resolve()
    cicd = Path(args.cicd_dir).resolve()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    policy = load_reliability(cicd, args.app_id)
    blocking = args.blocking.lower() == "true" and gate(policy, "postEmpalmeIntegrityRequired", True)

    port_map_path = Path(args.port_map) if args.port_map else web / ".lovable-port-map.json"
    port_map = load_port_map(port_map_path)

    errors: list[str] = []
    warnings: list[str] = []

    ui_paths = {
        str(f.get("path") or "")
        for f in manifest.get("changedFiles") or []
        if f.get("kind") == "ui"
    }
    for f in manifest.get("changedFiles") or []:
        if f.get("source") == "design-gap":
            ui_paths.add(str(f.get("path") or ""))

    forbidden = [re.compile(p, re.I) for p in (policy.get("forbiddenPatternsInBridgePages") or [])]
    deny_components = set(policy.get("denyAutoComponentsOnBridgePages") or [])
    for entry in policy.get("bridgePages") or []:
        deny_components.update(entry.get("denyAutoComponents") or [])

    max_delta = int((policy.get("gates") or {}).get("maxBridgePageLineDelta") or 400)

    checked_pages: set[str] = set()
    for lovable_rel in ui_paths:
        if not lovable_rel:
            continue
        bridge = bridge_page_for(lovable_rel, policy)
        web_rel = (bridge or {}).get("webPath") or map_lovable_to_web(lovable_rel, port_map) or ""
        if not web_rel or web_rel in checked_pages:
            continue
        if not bridge and "/pages/" not in web_rel:
            continue
        checked_pages.add(web_rel)

        web_path = web / web_rel
        if not web_path.is_file():
            warnings.append(f"Bridge page no encontrada: {web_rel}")
            continue

        text = web_path.read_text(encoding="utf-8", errors="replace")
        for pat in forbidden:
            if pat.search(text):
                errors.append(f"{web_rel}: import mock prohibido en página bridge")

        for comp in deny_components:
            if re.search(rf"<\s*{re.escape(comp)}\b", text):
                errors.append(f"{web_rel}: componente {comp} auto-insertado no permitido en bridge page")

        line_count = len(text.splitlines())
        if line_count > 2500:
            errors.append(f"{web_rel}: sospecha full_sync ({line_count} líneas > 2500)")
        elif line_count > max_delta + 800:
            warnings.append(f"{web_rel}: delta grande post-empalme ({line_count} líneas)")

        required_markers = policy.get("requiredBridgeMarkersInPages") or ["@doevents/shared"]
        if bridge and not any(m in text for m in required_markers):
            errors.append(f"{web_rel}: faltan marcadores bridge {required_markers}")

    result = {
        "ok": len(errors) == 0,
        "blocking": blocking,
        "errors": errors,
        "warnings": warnings,
        "checkedPages": sorted(checked_pages),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors and blocking:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
