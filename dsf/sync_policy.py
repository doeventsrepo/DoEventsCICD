"""Política de sync DSF — cicd.config.json + overrides dsf.properties."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from dsf.config import dsf_settings, load_config

DEFAULTS: dict[str, bool] = {
    "blockOnSimilarity": True,
    "adaptOnlyOnManifestChanges": False,
    "designComparisonInformational": False,
    "forceAgentBelowSimilarity": True,
}


def load_properties(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "yes", "1", "on"):
        return True
    if text in ("false", "no", "0", "off"):
        return False
    return default


def load_sync_policy(cicd_root: Path | None = None) -> dict[str, Any]:
    root = cicd_root or Path(__file__).resolve().parent.parent
    cfg = load_config(root)
    dsf = dsf_settings(cfg)
    base: dict[str, Any] = dict(dsf.get("syncPolicy") or {})

    props_name = str(base.get("propertiesFile") or "dsf.properties")
    props = load_properties(root / props_name)

    policy: dict[str, Any] = {"propertiesFile": props_name, "propertiesLoaded": props_name if props else None}

    for key, default in DEFAULTS.items():
        prop_key = f"dsf.syncPolicy.{key}"
        if prop_key in props:
            policy[key] = as_bool(props[prop_key], default)
        elif key in base:
            policy[key] = as_bool(base[key], default)
        elif key == "forceAgentBelowSimilarity" and "forceAgentBelowSimilarity" in dsf:
            policy[key] = as_bool(dsf["forceAgentBelowSimilarity"], default)
        else:
            policy[key] = default

    return policy


def manifest_has_sync_changes(manifest: dict[str, Any]) -> bool:
    return bool(manifest.get("hasUiChanges") or manifest.get("hasRulesChanges"))


def resolve_requires_agent(
    manifest: dict[str, Any],
    design: dict[str, Any] | None,
    policy: dict[str, Any] | None = None,
    *,
    target_similarity: float = 98.0,
) -> bool:
    """True si el job adapt debe ejecutarse en este run."""
    if policy is None:
        policy = load_sync_policy()

    if policy.get("adaptOnlyOnManifestChanges"):
        return manifest_has_sync_changes(manifest)

    sim = float((design or {}).get("overallSimilarityPercent", 100))
    force_below = bool(policy.get("forceAgentBelowSimilarity"))
    from_manifest = bool(manifest.get("requiresAgent"))
    from_design = bool((design or {}).get("requiresAgentForDesignAlignment"))
    if not policy.get("designComparisonInformational"):
        from_manifest = from_manifest or from_design
    return from_manifest or (force_below and sim < target_similarity)
