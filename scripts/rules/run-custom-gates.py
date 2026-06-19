#!/usr/bin/env python3
"""Ejecuta reglas custom DSF desde Reglas/custom/*.yml"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("custom_dir")
    parser.add_argument("--web-dir", default=".")
    args = parser.parse_args()

    custom = Path(args.custom_dir)
    if not custom.exists():
        print(json.dumps({"ok": True, "rules": [], "note": "Sin Reglas/custom"}))
        return 0

    if yaml is None:
        print("AVISO: PyYAML no instalado — skip custom rules", file=sys.stderr)
        return 0

    errors: list[str] = []
    checked: list[str] = []

    for rule_file in sorted(custom.glob("*.yml")):
        data = yaml.safe_load(rule_file.read_text(encoding="utf-8")) or {}
        name = data.get("name", rule_file.stem)
        checked.append(name)
        gate = data.get("gate", "warn")
        pattern = data.get("forbidPattern")
        scan_path = data.get("scanPath", "packages/shell/src/pages")
        if pattern:
            import re
            target = Path(args.web_dir) / scan_path
            if target.exists():
                for f in target.rglob("*"):
                    if f.is_file() and f.suffix in {".ts", ".tsx"}:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        if re.search(pattern, text):
                            msg = f"{name}: patrón prohibido en {f.relative_to(args.web_dir)}"
                            if gate == "block":
                                errors.append(msg)
                            else:
                                print(f"AVISO: {msg}", file=sys.stderr)

    result = {"ok": len(errors) == 0, "rulesChecked": checked, "errors": errors}
    print(json.dumps(result, indent=2))
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
