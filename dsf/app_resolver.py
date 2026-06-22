"""Resolución de configuración DSF por aplicación (registro empresarial)."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from dsf.config import load_config


class UnknownApplicationError(ValueError):
    pass


class ApplicationDisabledError(ValueError):
    pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def list_applications(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    apps = cfg.get("applications", {})
    registry = apps.get("registry", {})
    result: list[dict[str, Any]] = []
    for app_id, app in registry.items():
        result.append({
            "id": app_id,
            "displayName": app.get("displayName", app_id),
            "enabled": app.get("enabled", True),
            "designRepo": (app.get("repositories") or {}).get("design"),
            "frontendRepo": (app.get("repositories") or {}).get("frontend"),
        })
    return sorted(result, key=lambda x: x["id"])


def default_application_id(cfg: dict[str, Any]) -> str:
    apps = cfg.get("applications", {})
    if apps.get("default"):
        return str(apps["default"]).lower()
    project = str(cfg.get("project", "default")).lower().replace(" ", "-")
    return project


def _legacy_application(cfg: dict[str, Any], app_id: str) -> dict[str, Any]:
    repos = cfg.get("repositories", {})
    branches = cfg.get("branches", {})
    paths = cfg.get("paths", {})
    cloud = cfg.get("cloud", {})
    provider = cloud.get("defaultProvider", "aws")
    dev_cloud = cloud.get("providers", {}).get(provider, {}).get("dev", {})
    web = dev_cloud.get("web", {})
    return {
        "id": app_id,
        "displayName": cfg.get("project", app_id),
        "enabled": True,
        "repositories": {
            "design": repos.get("design"),
            "frontend": repos.get("frontend"),
            "backend": repos.get("backend"),
            "cicd": repos.get("cicd"),
        },
        "branches": {
            "design": branches.get("design", "main"),
            "webCicd": branches.get("cicdWeb") or branches.get("agentOutputBranch"),
        },
        "paths": {
            "lovableUi": paths.get("lovableUi", "src"),
            "webLovable": paths.get("webLovable"),
            "webBridge": paths.get("webBridge"),
            "portMap": cfg.get("dsfCore", {}).get("portMap", ".lovable-port-map.json"),
        },
        "deploy": {
            "devDomain": web.get("domain"),
            "buildCommand": dev_cloud.get("buildCommand", "npm run build:devaws"),
            "buildMode": dev_cloud.get("buildMode", "devaws"),
            "cloudProvider": provider,
            "cloudEnv": "dev",
            "webBucket": web.get("bucket"),
            "cloudFrontDistributionId": web.get("cloudFrontDistributionId"),
            "apiDomain": dev_cloud.get("api", {}).get("domain"),
        },
        "dsf": cfg.get("dsf", {}),
    }


def resolve_application(
    app_id: str | None = None,
    *,
    cicd_root: Path | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve configuración efectiva para una app del registro empresarial."""
    cfg = cfg or load_config(cicd_root)
    aid = (app_id or default_application_id(cfg)).strip().lower()
    registry = cfg.get("applications", {}).get("registry", {})

    if aid in registry:
        app = copy.deepcopy(registry[aid])
        if not app.get("enabled", True):
            raise ApplicationDisabledError(f"Aplicación inhabilitada: {aid}")
        app["id"] = aid
        legacy = _legacy_application(cfg, aid)
        merged = _deep_merge(legacy, app)
        merged["id"] = aid
        return merged

    # Compatibilidad: una sola app sin registro explícito
    default_id = default_application_id(cfg)
    if aid == default_id and cfg.get("repositories"):
        return _legacy_application(cfg, aid)

    raise UnknownApplicationError(
        f"Aplicación desconocida: {aid}. Registradas: {', '.join(sorted(registry)) or '(ninguna)'}"
    )


def application_env(app: dict[str, Any]) -> dict[str, str]:
    """Variables para GitHub Actions / scripts shell."""
    repos = app.get("repositories", {})
    branches = app.get("branches", {})
    deploy = app.get("deploy", {})
    return {
        "app_id": app["id"],
        "design_repo": repos.get("design", ""),
        "web_repo": repos.get("frontend", ""),
        "back_repo": repos.get("backend", ""),
        "cicd_repo": repos.get("cicd", ""),
        "design_branch": branches.get("design", "main"),
        "web_cicd_branch": branches.get("webCicd", "feature/cicd/dev-automation"),
        "deploy_dev_domain": deploy.get("devDomain", ""),
        "build_command": deploy.get("buildCommand", "npm run build:devaws"),
        "api_domain": deploy.get("apiDomain", ""),
    }
