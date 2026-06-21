"""Resolución de rutas Lovable → WEB según .lovable-port-map.json."""
from __future__ import annotations

import json
from pathlib import Path


def load_port_map(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict] = []
    for raw in data.get("mapping", []):
        lovable = raw["lovable"].replace("\\", "/")
        web = raw["web"].replace("\\", "/")
        is_exact = not lovable.endswith("/") and "." in Path(lovable).name
        prefix_lovable = lovable if is_exact else (lovable if lovable.endswith("/") else f"{lovable}/")
        prefix_web = web if is_exact else (web if web.endswith("/") else f"{web}/")
        items.append(
            {
                "lovable": lovable,
                "web": web,
                "isExact": is_exact,
                "prefixLovable": prefix_lovable,
                "prefixWeb": prefix_web,
                "compareMode": raw.get("compareMode", ""),
                "note": raw.get("note", ""),
            }
        )
    items.sort(key=lambda i: len(i["lovable"]), reverse=True)
    return items


def map_lovable_to_web(relative: str, items: list[dict]) -> str | None:
    rel = relative.replace("\\", "/")
    for item in items:
        if item["isExact"]:
            if rel == item["lovable"]:
                return item["web"]
        elif rel.startswith(item["prefixLovable"]) and item["prefixLovable"].startswith("src/"):
            return item["prefixWeb"] + rel[len(item["prefixLovable"]) :]
    return None


def mapping_for(relative: str, items: list[dict]) -> dict | None:
    rel = relative.replace("\\", "/")
    for item in items:
        if item["isExact"] and rel == item["lovable"]:
            return item
        if not item["isExact"] and rel.startswith(item["prefixLovable"]):
            return item
    return None
