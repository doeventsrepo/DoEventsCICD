"""Política de fiabilidad DSF — multi-app (cicd.config.json + overrides por app)."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from dsf.config import dsf_settings, load_config

DEFAULTS: dict[str, Any] = {
    "version": "1.0",
    "syncAttempts": 2,
    "retryDelaySeconds": 60,
    "gates": {
        "portMapDuplicateHeuristicBlocks": False,
        "bridgeCanaryRequired": True,
        "postEmpalmeBuildRequired": True,
        "postEmpalmeIntegrityRequired": True,
        "smokeRequired": True,
        "maxDesignGapInjectionsPerRun": 6,
        "skipDesignGapOnRulesOnlyPush": True,
        "maxBridgePageLineDelta": 400,
    },
    "denyAutoComponentsOnBridgePages": ["FeedBanner"],
    "bridgePageInsertAnchors": ["FeedServicesCarousel", "FeedVenuesCarousel"],
    "bridgePages": [],
    "requiredBridgeMarkersInPages": ["@doevents/shared"],
    "forbiddenPatternsInBridgePages": [
        r"from\s+['\"]@lovable/data/mock",
        r"from\s+['\"]@/data/mock",
    ],
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, val in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(val, dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_reliability(cicd_root: Path | None = None, app_id: str | None = None) -> dict[str, Any]:
    root = cicd_root or Path(__file__).resolve().parent.parent
    cfg = load_config(root)
    policy = _deep_merge(DEFAULTS, dict(dsf_settings(cfg).get("reliability") or {}))

    if app_id:
        registry = (cfg.get("applications") or {}).get("registry") or {}
        app_cfg = registry.get(app_id) or {}
        if app_cfg.get("reliability"):
            policy = _deep_merge(policy, app_cfg["reliability"])

    defaults_file = root / "dsf" / "reliability-policy.defaults.json"
    if defaults_file.is_file():
        import json

        file_defaults = json.loads(defaults_file.read_text(encoding="utf-8"))
        policy = _deep_merge(file_defaults, policy)

    return policy


def gate(policy: dict[str, Any], name: str, default: bool = True) -> bool:
    gates = policy.get("gates") or {}
    val = gates.get(name, default)
    return bool(val) if not isinstance(val, str) else val.lower() in ("true", "1", "yes", "on")


def bridge_page_for(lovable_path: str, policy: dict[str, Any]) -> dict[str, Any] | None:
    lp = lovable_path.replace("\\", "/").lstrip("./")
    for entry in policy.get("bridgePages") or []:
        if str(entry.get("lovablePath", "")).replace("\\", "/") == lp:
            return entry
    return None


def deny_auto_components(policy: dict[str, Any]) -> frozenset[str]:
    deny = set(policy.get("denyAutoComponentsOnBridgePages") or [])
    for entry in policy.get("bridgePages") or []:
        deny.update(entry.get("denyAutoComponents") or [])
    return frozenset(deny)


def insert_anchors_for_bridge(policy: dict[str, Any], lovable_path: str) -> list[str]:
    entry = bridge_page_for(lovable_path, policy)
    if entry and entry.get("insertAfterComponents"):
        return list(entry["insertAfterComponents"])
    return list(policy.get("bridgePageInsertAnchors") or [])
