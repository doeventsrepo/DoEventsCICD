#!/usr/bin/env python3
"""DSF Gate G0 — Valida que archivos Lovable relevantes tengan cobertura en port-map."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TRACK_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".css"}
SKIP_PREFIXES = (
    "src/components/ui/",
    "src/integrations/",
    "src/test/",
    "src/lib/",
    "src/data/",
    "src/services/",
    "src/types/",
    "src/utils/",
    "src/vite-env.d.ts",
)
SKIP_FILES = {"src/App.tsx", "src/main.tsx", "src/App.css", "src/index.css"}


def load_port_map(path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: list[tuple[str, str]] = []
    for item in data.get("mapping", []):
        lovable = item["lovable"].replace("\\", "/")
        web = item["web"].replace("\\", "/")
        if not lovable.endswith("/") and not lovable.endswith(".tsx") and not lovable.endswith(".ts"):
            lovable += "/"
        mapping.append((lovable, web))
    forbidden = [f.replace("\\", "/") for f in data.get("forbidden", [])]
    exclude = [e.replace("\\", "/").rstrip("*") for e in data.get("exclude", [])]
    forbidden = list(dict.fromkeys(forbidden + exclude))
    return mapping, forbidden


def is_mapped(relative: str, mapping: list[tuple[str, str]], forbidden: list[str]) -> bool:
    rel = relative.replace("\\", "/")
    if rel in SKIP_FILES:
        return True
    if any(rel.startswith(p) for p in SKIP_PREFIXES):
        return True
    if any(rel.startswith(f) for f in forbidden):
        return True
    if Path(rel).suffix.lower() not in TRACK_EXTENSIONS:
        return True
    for lovable_prefix, _ in mapping:
        if rel == lovable_prefix.rstrip("/") or rel.startswith(lovable_prefix):
            return True
    return False


def collect_lovable_files(lovable_root: Path) -> list[str]:
    src = lovable_root / "src"
    if not src.exists():
        return []
    files: list[str] = []
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(lovable_root).as_posix()
        if rel.startswith("src/"):
            files.append(rel)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lovable_dir")
    parser.add_argument("port_map")
    parser.add_argument("--manifest", default="", help="Solo validar archivos del manifiesto")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    lovable_root = Path(args.lovable_dir)
    port_map_path = Path(args.port_map)
    mapping, forbidden = load_port_map(port_map_path)

    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        candidates = [f["path"] for f in manifest.get("changedFiles", []) if f.get("kind") in ("ui", "rules")]
    else:
        candidates = collect_lovable_files(lovable_root)

    unmapped: list[str] = []
    for rel in candidates:
        if not is_mapped(rel, mapping, forbidden):
            unmapped.append(rel)

    result = {
        "ok": len(unmapped) == 0,
        "checked": len(candidates),
        "unmapped": unmapped,
        "unmappedCount": len(unmapped),
    }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if unmapped:
        print("ERROR: archivos sin cobertura en port-map:", file=sys.stderr)
        for u in unmapped[:30]:
            print(f"  - {u}", file=sys.stderr)
        if len(unmapped) > 30:
            print(f"  ... y {len(unmapped) - 30} más", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
