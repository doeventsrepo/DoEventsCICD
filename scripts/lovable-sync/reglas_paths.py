"""Resuelve rutas de Reglas/ desde cicd.config.json y reglas.config.json."""
from __future__ import annotations

import json
from pathlib import Path

AGENT_DIR = "ReglasAgente"
DEFAULT_CICD_ROOT = Path(__file__).resolve().parents[2]


def cicd_root(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = __import__("os").environ.get("CICD_DIR")
    return Path(env).resolve() if env else DEFAULT_CICD_ROOT


def load_reglas_config(root: Path | None = None) -> dict:
    root = root or cicd_root()
    path = root / "Reglas" / "reglas.config.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def operativas_paths(root: Path | None = None) -> dict[str, Path]:
    root = root or cicd_root()
    cfg = load_reglas_config(root)
    ops = cfg.get("operativas", {})
    return {
        "reglamento": root / ops.get("reglamento", "Reglas/operativas/reglamento-cursor-api.md"),
        "promptEmpalme": root / ops.get("promptEmpalme", "Reglas/operativas/prompt-empalme-web.md"),
        "promptFullstack": root / ops.get("promptFullstack", "Reglas/operativas/prompt-fullstack.md"),
    }


def artefactos_dir(root: Path | None = None) -> Path:
    root = root or cicd_root()
    cfg = load_reglas_config(root)
    rel = cfg.get("artefactosWeb", {}).get("templatesDir", "Reglas/artefactos-web")
    return root / rel


def min_reglas_front_bytes(root: Path | None = None) -> int:
    cfg = load_reglas_config(root or cicd_root())
    return int(cfg.get("artefactosWeb", {}).get("minReglasFrontBytes", 500))
