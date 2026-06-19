"""Carga cicd.config.json y expone configuración DSF."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(cicd_root: Path | None = None) -> dict[str, Any]:
    root = cicd_root or Path(__file__).resolve().parent.parent
    path = root / "cicd.config.json"
    if not path.exists():
        raise FileNotFoundError(f"No se encontró {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def dsf_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("dsf", {})


def cloud_provider(cfg: dict[str, Any], env: str = "dev") -> dict[str, Any]:
    provider = cfg.get("cloud", {}).get("defaultProvider", "aws")
    return cfg.get("cloud", {}).get("providers", {}).get(provider, {}).get(env, {})


def qa_promotion_enabled(cfg: dict[str, Any]) -> bool:
    return bool(dsf_settings(cfg).get("qaPromotion", {}).get("enabled", False))
