#!/usr/bin/env python3
"""Valida que Reglas/ tenga la estructura minima para el agente Cursor."""
from __future__ import annotations

import sys
from pathlib import Path

from reglas_paths import artefactos_dir, load_reglas_config, min_reglas_front_bytes, operativas_paths


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    cfg = load_reglas_config(root)
    if not cfg:
        print(f"ERROR: falta {root / 'Reglas/reglas.config.json'}", file=sys.stderr)
        return 1

    errors: list[str] = []
    ops = operativas_paths(root)
    for key, path in ops.items():
        if not path.is_file() or path.stat().st_size < 100:
            errors.append(f"Falta o vacio: {path.relative_to(root)} ({key})")

    art = artefactos_dir(root)
    for name in cfg.get("artefactosWeb", {}).get("files", []):
        p = art / name
        if not p.is_file():
            errors.append(f"Falta artefacto: {p.relative_to(root)}")

    front = art / "reglas-front.md"
    min_bytes = min_reglas_front_bytes(root)
    if front.is_file() and len(front.read_text(encoding="utf-8").strip()) < min_bytes:
        errors.append(f"reglas-front.md plantilla < {min_bytes} bytes")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1

    print(f"OK: Reglas/ valido ({len(ops)} operativas, {len(cfg.get('artefactosWeb', {}).get('files', []))} artefactos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
