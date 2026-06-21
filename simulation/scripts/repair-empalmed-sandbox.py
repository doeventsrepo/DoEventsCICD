#!/usr/bin/env python3
"""Re-sincroniza archivos empalados en sandbox con transform corregido."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SIM = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("local_apply", SIM / "local-apply-empalme.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)
transform = mod.transform_lovable_source


def main() -> int:
    lovable = Path(r"C:\DoEvents\AplicacionWEB\discover-joyful-feed")
    web = Path(r"C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation\sandbox\DoEventsWEB")
    reports = [
        Path(r"C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation\output\dsf-local\local-iter-20260620-001\local-empalme-report.json"),
        Path(r"C:\DoEvents\AplicacionWEB\DoEventsCICD\simulation\output\dsf-local\local-final-20260620\local-empalme-round-1.json"),
    ]
    paths: set[tuple[str, str]] = set()
    for rp in reports:
        if not rp.exists():
            continue
        data = json.loads(rp.read_text(encoding="utf-8"))
        for item in data.get("applied") or []:
            paths.add((item["lovablePath"], item["webPath"]))

    fixed = 0
    for lrel, wrel in sorted(paths):
        src = lovable / lrel
        dst = web / wrel
        if not src.is_file():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(transform(src.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
        fixed += 1
    print(json.dumps({"repairedFiles": fixed}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
