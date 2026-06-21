#!/usr/bin/env python3
"""Compara diseño Lovable (discover-joyful-feed) vs DoEventsWEB — similitud y gaps."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from design_normalize import (
    MOCK_MARKERS,
    file_similarity,
    resolve_web_comparison_content,
)
from design_tokens import hardcoded_color_violations, load_design_tokens, semantic_token_score, token_metadata
from design_validation_hints import attach_validation_to_comparison
from port_map_utils import is_excluded, load_port_map, load_port_map_data, map_lovable_to_web, mapping_for

DESIGN_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".css"}
SKIP_LOVABLE_PREFIXES = (
    "src/components/ui/",
    "src/integrations/",
    "src/test/",
)
def should_track(relative: str) -> bool:
    rel = relative.replace("\\", "/")
    if not rel.startswith("src/"):
        return False
    if any(rel.startswith(p) for p in SKIP_LOVABLE_PREFIXES):
        return False
    return Path(rel).suffix.lower() in DESIGN_EXTENSIONS


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
    port_map_data = load_port_map_data(port_map_path)
    design_tokens = load_design_tokens(lovable_root)
    tokens_meta = token_metadata(design_tokens)
    lovable_files = collect_lovable_design_files(lovable_root)

    entries: list[dict] = []
    missing_in_web: list[str] = []
    low_similarity: list[dict] = []
    similarity_sum = 0.0
    tracked = 0

    for rel in lovable_files:
        if is_excluded(rel, port_map_data):
            continue
        web_rel = map_lovable_to_web(rel, mapping)
        if not web_rel:
            continue
        meta = mapping_for(rel, mapping) or {}
        compare_mode = meta.get("compareMode", "")
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

        if compare_mode == "delegated" or "mfe-auth" in web_rel.replace("\\", "/"):
            ratio = 1.0
            pct = 100.0
            status = "aligned"
        else:
            web_content = web_path.read_text(encoding="utf-8", errors="replace")
            web_compare = resolve_web_comparison_content(web_root, web_rel, web_content)
            ratio = file_similarity(lovable_content, web_compare)
            # Ponderar tokens semánticos (reglasDiseno/tokens.yml)
            token_factor = (semantic_token_score(lovable_content) + semantic_token_score(web_compare)) / 2
            ratio = ratio * 0.85 + ratio * token_factor * 0.15
            pct = round(ratio * 100, 2)
            status = "aligned"
            if pct < 85:
                status = "needs_adaptation"
                low_similarity.append({"lovablePath": rel, "webPath": web_rel, "similarityPercent": pct})
            elif pct < 98:
                status = "minor_drift"

        web_content = web_path.read_text(encoding="utf-8", errors="replace")
        has_mock_lovable = bool(MOCK_MARKERS.search(lovable_content))
        has_mock_web = bool(MOCK_MARKERS.search(web_content))

        entry = {
            "lovablePath": rel,
            "webPath": web_rel,
            "status": status,
            "similarityPercent": pct,
            "compareMode": compare_mode or ("delegated" if "mfe-auth" in web_rel else "structural"),
            "lovableHasMockPatterns": has_mock_lovable,
            "webHasMockPatterns": has_mock_web,
            "lovableHardcodedColors": hardcoded_color_violations(lovable_content)[:5],
            "webHardcodedColors": hardcoded_color_violations(web_content)[:5],
            "action": "review_empalme" if status != "aligned" else "none",
        }
        entries.append(entry)
        similarity_sum += ratio
        tracked += 1

    overall = round((similarity_sum / tracked * 100) if tracked else 100.0, 2)
    target = 98.0
    requires_agent = overall < target or len(missing_in_web) > 0 or len(low_similarity) > 0

    report = {
        "version": "1.2",
        "purpose": "Comparacion diseño Lovable vs DoEventsWEB (empalme, mocks excluidos, reglasDiseno/tokens)",
        "designTokens": tokens_meta,
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
