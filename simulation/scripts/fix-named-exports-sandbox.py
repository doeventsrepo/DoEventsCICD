#!/usr/bin/env python3
"""Añade export nombrado cuando un componente solo tiene export default (build Rollup)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "sandbox" / "DoEventsWEB" / "packages" / "shell" / "src" / "lovable"


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^export default (\w+)\s*;", text, re.MULTILINE)
    if not m:
        return False
    name = m.group(1)
    if re.search(rf"^export const {name}\b", text, re.MULTILINE):
        return False
    if re.search(rf"^export function {name}\b", text, re.MULTILINE):
        return False
    new_text, n = re.subn(
        rf"^const {name} = ",
        f"export const {name} = ",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    fixed = []
    for path in sorted(ROOT.rglob("*.tsx")):
        if fix_file(path):
            fixed.append(str(path.relative_to(ROOT)))
    print(f"fixed {len(fixed)} files")
    for p in fixed[:50]:
        print(f"  - {p}")
    if len(fixed) > 50:
        print(f"  ... +{len(fixed) - 50} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
