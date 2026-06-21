"""Carga reglasDiseno/tokens.yml para comparación DSF."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

HARDCODED_COLOR = re.compile(
    r"(?:text-white|bg-black|bg-\[#|text-\[#|style=\{\{[^}]*(?:color|background)\s*:\s*['\"]#)",
    re.I,
)
SEMANTIC_TOKEN = re.compile(
    r"\b(?:bg|text|border|ring|from|to|via)-(?:primary|secondary|muted|accent|destructive|success|warning|foreground|background|card|favorite|border|input)\b",
)


def load_design_tokens(lovable_root: Path) -> dict[str, Any]:
    path = lovable_root / "reglasDiseno" / "tokens.yml"
    if not path.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def hardcoded_color_violations(text: str) -> list[str]:
    return [m.group(0) for m in HARDCODED_COLOR.finditer(text)]


def semantic_token_score(text: str) -> float:
    """0–1: uso de clases semánticas vs hardcoded."""
    hard = len(hardcoded_color_violations(text))
    semantic = len(SEMANTIC_TOKEN.findall(text))
    if hard == 0 and semantic == 0:
        return 1.0
    if hard > 0:
        return max(0.0, 1.0 - hard * 0.15)
    return min(1.0, 0.85 + semantic * 0.01)


def token_metadata(tokens: dict[str, Any]) -> dict[str, Any]:
    if not tokens:
        return {"loaded": False}
    colors = tokens.get("colors") or {}
    return {
        "loaded": True,
        "id": tokens.get("id"),
        "version": tokens.get("version"),
        "fontFamily": (tokens.get("typography") or {}).get("fontFamily"),
        "radiusBase": (tokens.get("radius") or {}).get("base"),
        "colorTokenCount": len([k for k in colors if k != "dark"]),
        "reglas": tokens.get("reglas") or [],
    }
