#!/usr/bin/env python3
"""Copia src/data y src/lib de Lovable al sandbox WEB (solo disco local)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

LOVABLE = Path(r"C:\DoEvents\AplicacionWEB\discover-joyful-feed\src")
WEB_LOVABLE = Path(
    r"C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation\sandbox\DoEventsWEB\packages\shell\src\lovable"
)


SUBDIRS = ("data", "lib", "services", "hooks", "types", "utils")


def transform(text: str) -> str:
    text = re.sub(
        r'from (["\'])(@/[^"\']+)\1',
        lambda m: f"from {m.group(1)}{('@lovable/' + m.group(2)[2:]) if m.group(2).startswith('@/') else m.group(2)}{m.group(1)}",
        text,
    )
    text = re.sub(
        r'import (["\'])(@/[^"\']+)\1',
        lambda m: f"import {m.group(1)}{('@lovable/' + m.group(2)[2:]) if m.group(2).startswith('@/') else m.group(2)}{m.group(1)}",
        text,
    )
    return text


def sync_dir(sub: str) -> int:
    src_dir = LOVABLE / sub
    dst_dir = WEB_LOVABLE / sub
    dst_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for path in src_dir.glob("*"):
        if not path.is_file():
            continue
        dst = dst_dir / path.name
        dst.write_text(transform(path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        n += 1
    return n


def main() -> int:
    total = 0
    for sub in SUBDIRS:
        src_dir = LOVABLE / sub
        if src_dir.is_dir():
            total += sync_dir(sub)
    print(f"OK local sync: {total} archivos -> {WEB_LOVABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
