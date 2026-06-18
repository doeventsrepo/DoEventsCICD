#!/usr/bin/env python3
"""Bloquea sync/adaptacion si ReglasAgente/reglas-front.md no existe o esta vacio."""
from __future__ import annotations

import sys
from pathlib import Path

MIN_BYTES = 500


def main() -> int:
    web = Path(sys.argv[1] if len(sys.argv) > 1 else "DoEventsWEB")
    rules = web / "ReglasAgente" / "reglas-front.md"
    if not rules.exists():
        print(f"BLOQUEADO: falta {rules}", file=sys.stderr)
        print("El agente no puede adaptar codigo sin ReglasAgente/reglas-front.md", file=sys.stderr)
        return 1
    content = rules.read_text(encoding="utf-8").strip()
    if len(content) < MIN_BYTES:
        print(f"BLOQUEADO: {rules} incompleto ({len(content)} bytes)", file=sys.stderr)
        return 1
    print(f"OK: reglas del agente presentes ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
