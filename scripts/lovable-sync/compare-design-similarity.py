#!/usr/bin/env python3
"""Compara diseño Lovable (discover-joyful-feed) vs DoEventsWEB — similitud y gaps."""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

from design_validation_hints import attach_validation_to_comparison

DESIGN_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".css"}
SKIP_LOVABLE_PREFIXES = (
    "src/components/ui/",
    "src/integrations/",
    "src/test/",
)
MOCK_MARKERS = re.compile(
    r"mock(?:Data|Users|Events|Tickets|Orders)?|sampleData|hardcodedEvents|fakeData",
    re.I,
)


def load_port_map(path: Path) -> list[tuple[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs: list[tuple[str, str]] = []
    for item in data.get("mapping", []):
        lovable = item["lovable"].replace("\\", "/")
        web = item["web"].replace("\\", "/")
        if not lovable.endswith("/"):
            lovable += "/"
        if not web.endswith("/"):
            web += "/"
        pairs.append((lovable, web))
    return pairs


def map_lovable_to_web(relative: str, mapping: list[tuple[str, str]]) -> str | None:
    rel = relative.replace("\\", "/")
    for lovable_prefix, web_prefix in mapping:
        if rel.startswith(lovable_prefix) and lovable_prefix.startswith("src/"):
            return web_prefix + rel[len(lovable_prefix) :]
    return None


def should_track(relative: str) -> bool:
    rel = relative.replace("\\", "/")
    if not rel.startswith("src/"):
        return False
    if any(rel.startswith(p) for p in SKIP_LOVABLE_PREFIXES):
        return False
    return Path(rel).suffix.lower() in DESIGN_EXTENSIONS


def normalize_source(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("/*") or s.startswith("*"):
            continue
        if s.startswith("import ") or s.startswith("export type ") and " from " in s:
            continue
        lines.append(s)
    return "\n".join(lines)


def file_similarity(lovable_text: str, web_text: str) -> float:
    a = normalize_source(lovable_text)
    b = normalize_source(web_text)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def collect_lovable_design_files(lovable_root: Path) -> list[str]:
    files: list[str] = []
    src = lovable_root / "src"
    if not src.exists():
        return files
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(lovable_root).as_posix()
        if should_track(rel):
            files.append(rel)
    return sorted(files)


def main() -> int:
    if len(sys.argv) < 4:
        print(
            "Uso: compare-design-similarity.py <lovable_dir> <web_dir> <port_map.json> [out.json]",
            file=sys.stderr,
        )
        return 1

    lovable_root = Path(sys.argv[1]).resolve()
    web_root = Path(sys.argv[2]).resolve()
    port_map_path = Path(sys.argv[3]).resolve()
    out_path = Path(sys.argv[4]).resolve() if len(sys.argv) > 4 else lovable_root / "design-comparison.json"

    mapping = load_port_map(port_map_path)
    lovable_files = collect_lovable_design_files(lovable_root)

    entries: list[dict] = []
    missing_in_web: list[str] = []
    low_similarity: list[dict] = []
    similarity_sum = 0.0
    tracked = 0

    for rel in lovable_files:
        web_rel = map_lovable_to_web(rel, mapping)
        if not web_rel:
            continue
        web_path = web_root / web_rel
        lovable_path = lovable_root / rel
        lovable_content = lovable_path.read_text(encoding="utf-8", errors="replace")

        if not web_path.is_file():
            entry = {
                "lovablePath": rel,
                "webPath": web_rel,
                "status": "missing_in_web",
                "similarityPercent": 0.0,
                "action": "implement_via_empalme",
            }
            entries.append(entry)
            missing_in_web.append(rel)
            similarity_sum += 0.0
            tracked += 1
            continue

        web_content = web_path.read_text(encoding="utf-8", errors="replace")
        ratio = file_similarity(lovable_content, web_content)
        pct = round(ratio * 100, 2)
        has_mock_lovable = bool(MOCK_MARKERS.search(lovable_content))
        has_mock_web = bool(MOCK_MARKERS.search(web_content))

        status = "aligned"
        if pct < 85:
            status = "needs_adaptation"
            low_similarity.append({"lovablePath": rel, "webPath": web_rel, "similarityPercent": pct})
        elif pct < 98:
            status = "minor_drift"

        entry = {
            "lovablePath": rel,
            "webPath": web_rel,
            "status": status,
            "similarityPercent": pct,
            "lovableHasMockPatterns": has_mock_lovable,
            "webHasMockPatterns": has_mock_web,
            "action": "review_empalme" if status != "aligned" else "none",
        }
        entries.append(entry)
        similarity_sum += ratio
        tracked += 1

    overall = round((similarity_sum / tracked * 100) if tracked else 100.0, 2)
    target = 98.0
    requires_agent = overall < target or len(missing_in_web) > 0 or len(low_similarity) > 0

    report = {
        "version": "1.0",
        "purpose": "Comparacion diseño Lovable vs DoEventsWEB (empalme, no copy-paste)",
        "lovableRoot": str(lovable_root),
        "webRoot": str(web_root),
        "trackedFiles": tracked,
        "overallSimilarityPercent": overall,
        "targetSimilarityPercent": target,
        "alignmentGapPercent": round(max(0.0, target - overall), 2),
        "missingInWebCount": len(missing_in_web),
        "needsAdaptationCount": len(low_similarity),
        "requiresAgentForDesignAlignment": requires_agent,
        "missingInWeb": missing_in_web[:50],
        "lowSimilarity": low_similarity[:50],
        "files": entries,
        "summary": {
            "aligned": sum(1 for e in entries if e["status"] == "aligned"),
            "minorDrift": sum(1 for e in entries if e["status"] == "minor_drift"),
            "needsAdaptation": sum(1 for e in entries if e["status"] == "needs_adaptation"),
            "missingInWeb": len(missing_in_web),
        },
    }

    report = attach_validation_to_comparison(report)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"overallSimilarityPercent": overall, "requiresAgent": requires_agent}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
