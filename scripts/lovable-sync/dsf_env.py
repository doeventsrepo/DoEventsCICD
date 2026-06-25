"""Carga secretos DSF/BSF — misma CURSOR_API_KEY que empalme y gap-loop."""
from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "=" not in line:
        return None
    key, _, val = line.partition("=")
    key = key.strip()
    val = val.strip().strip('"').strip("'")
    if not key or not val:
        return None
    return key, val


def load_dsf_secrets(cicd: Path | None = None) -> str | None:
    """
    Carga CURSOR_API_KEY si no está en os.environ.
    Retorna la fuente usada o None.
    """
    if os.environ.get("CURSOR_API_KEY"):
        return "session"

    if cicd is None:
        cicd = Path(__file__).resolve().parents[2]

    candidates: list[tuple[str, Path]] = [
        ("simulation/local.env", cicd / "simulation" / "local.env"),
        (
            "ConfiguracionEntorno/.local/dsf-secrets.env",
            cicd.parent / "ConfiguracionEntorno" / ".local" / "dsf-secrets.env",
        ),
    ]

    for label, path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, val = parsed
            if key == "CURSOR_API_KEY" and not os.environ.get(key):
                os.environ[key] = val
                return label
            if not os.environ.get(key):
                os.environ[key] = val

    return None
