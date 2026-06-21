#!/usr/bin/env python3
"""
Empalme local Lovable → sandbox WEB sin Cursor API ni push a GitHub.

Transforma imports @/ → @lovable/, elimina bloques MOCK_* y escribe en la ruta WEB del port-map.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CICD_ROOT / "scripts" / "lovable-sync"))

from design_normalize import strip_mock_blocks  # noqa: E402

SKIP_PREFIXES = ("src/pages/Login", "src/pages/SignUp", "src/pages/ForgotPassword", "src/pages/ResetPassword")
REEXPORT_MARKERS = ("export {", "export *", "export default")


def rewrite_imports(text: str) -> str:
    def repl_from(m: re.Match[str]) -> str:
        q, path = m.group(1), m.group(2)
        if path.startswith("@/"):
            path = "@lovable/" + path[2:]
        return f"from {q}{path}{q}"

    def repl_bare(m: re.Match[str]) -> str:
        q, path = m.group(1), m.group(2)
        if path.startswith("@/"):
            path = "@lovable/" + path[2:]
        return f"import {q}{path}{q}"

    text = re.sub(r'from (["\'])(@/[^"\']+)\1', repl_from, text)
    text = re.sub(r'import (["\'])(@/[^"\']+)\1', repl_bare, text)
    return text


def transform_lovable_source(text: str) -> str:
    text = strip_mock_blocks(text)
    text = re.sub(r"interface Mock(\w+)", r"interface \1Row", text)
    text = re.sub(r": Mock(\w+)", r": \1Row", text)
    text = re.sub(r"<Mock(\w+)", r"<\1Row", text)
    text = rewrite_imports(text)
    text = re.sub(r"import\s+\w+\s+from\s+['\"]@/assets/[^'\"]+['\"];\n?", "", text)
    return text


def is_reexport_stub(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    if not lines or len(lines) > 20:
        return False
    return all(any(m in ln for m in REEXPORT_MARKERS) for ln in lines)


def load_gaps(comparison_path: Path, *, min_sim: float, max_items: int) -> list[dict]:
    data = json.loads(comparison_path.read_text(encoding="utf-8"))
    gaps: list[dict] = []
    for entry in data.get("files") or []:
        sim = float(entry.get("similarityPercent", 0))
        status = entry.get("status", "")
        if status == "aligned" or sim >= min_sim:
            continue
        gaps.append(entry)
    gaps.sort(key=lambda g: float(g.get("similarityPercent", 0)))
    return gaps[:max_items]


def main() -> int:
    parser = argparse.ArgumentParser(description="Empalme local sin API")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--min-sim", type=float, default=85.0, help="Solo archivos bajo este %")
    parser.add_argument("--max-items", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    lovable_root = Path(args.lovable_dir).resolve()
    web_root = Path(args.web_dir).resolve()
    gaps = load_gaps(Path(args.comparison).resolve(), min_sim=args.min_sim, max_items=args.max_items)

    applied: list[dict] = []
    skipped: list[dict] = []

    for gap in gaps:
        lovable_rel = gap.get("lovablePath", "")
        web_rel = gap.get("webPath", "")
        if any(lovable_rel.startswith(p) for p in SKIP_PREFIXES):
            skipped.append({"lovablePath": lovable_rel, "reason": "auth_mfe_delegated"})
            continue
        lovable_path = lovable_root / lovable_rel
        web_path = web_root / web_rel
        if not lovable_path.is_file():
            skipped.append({"lovablePath": lovable_rel, "reason": "missing_lovable"})
            continue

        lovable_src = lovable_path.read_text(encoding="utf-8", errors="replace")
        web_exists = web_path.is_file()
        web_src = web_path.read_text(encoding="utf-8", errors="replace") if web_exists else ""

        if is_reexport_stub(web_src):
            skipped.append({"lovablePath": lovable_rel, "reason": "bridge_reexport_preserved"})
            continue

        should_apply = (
            not web_exists
            or float(gap.get("similarityPercent", 0)) < args.min_sim
        )
        if not should_apply:
            skipped.append({"lovablePath": lovable_rel, "reason": "partial_empalme_keep"})
            continue

        transformed = transform_lovable_source(lovable_src)
        if args.dry_run:
            applied.append({"lovablePath": lovable_rel, "webPath": web_rel, "dryRun": True})
            continue

        web_path.parent.mkdir(parents=True, exist_ok=True)
        web_path.write_text(transformed, encoding="utf-8")
        applied.append({"lovablePath": lovable_rel, "webPath": web_rel, "bytes": len(transformed)})

    report = {
        "appliedCount": len(applied),
        "skippedCount": len(skipped),
        "applied": applied,
        "skipped": skipped[:30],
    }
    print(json.dumps(report, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
