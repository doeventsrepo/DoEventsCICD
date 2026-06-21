#!/usr/bin/env python3
"""Agente refinamiento reglas — detecta UI sin reglaActuacion y propone borradores YAML."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agent_base import artifacts_dir, gh_output, is_dry_run, write_report

PAGE_DIRS = ("src/pages", "src/components")
RULES_DIR = "reglasActuacion"
SKIP_PREFIXES = ("src/components/ui/",)


def collect_ui_files(lovable_dir: Path) -> list[Path]:
    files: list[Path] = []
    for sub in PAGE_DIRS:
        d = lovable_dir / sub
        if d.exists():
            files.extend(sorted(d.rglob("*.tsx")))
    return files


def collect_rule_sources(lovable_dir: Path) -> set[str]:
    sources: set[str] = set()
    rules = lovable_dir / RULES_DIR
    if not rules.exists():
        return sources
    for yml in list(rules.rglob("*.yml")) + list(rules.rglob("*.yaml")):
        text = yml.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("- src/") or line.startswith("src/"):
                src = line.lstrip("- ").strip().strip('"').strip("'")
                sources.add(src.replace("\\", "/"))
    return sources


def domain_from_path(rel: str) -> str:
    parts = rel.split("/")
    if "admin" in parts:
        return "admin"
    if "pages" in parts and len(parts) > 2:
        name = parts[-1].replace(".tsx", "").lower()
        for d in ("event", "ticket", "user", "pay", "venue", "service", "chat"):
            if d in name:
                return {"event": "eventos", "ticket": "tickets", "user": "usuarios", "pay": "pagos",
                        "venue": "lugares", "service": "servicios", "chat": "chat"}.get(d, "general")
    return "general"


def draft_yaml(rel_path: str) -> str:
    stem = Path(rel_path).stem
    slug = stem[0].lower() + stem[1:] if stem else "component"
    domain = domain_from_path(rel_path)
    return f"""id: {domain}.{slug}
version: "1.0.0"
domain: {domain}
description: >
  Regla pendiente — componente detectado sin reglaActuacion asociada.
  Revisar y completar por diseñador antes de merge.

source:
  - {rel_path}

metadata:
  owner: producto
  priority: medium
  tags: [draft, dsf-auto, needs-human-approval]
  generatedBy: run-rules-refinement-agent.py
"""


def main() -> int:
    lovable_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LOVABLE_DIR", "."))
    ui_files = collect_ui_files(lovable_dir)
    covered = collect_rule_sources(lovable_dir)

    missing: list[dict] = []
    drafts_dir = artifacts_dir() / "rules-refinement-drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    for f in ui_files:
        rel = str(f.relative_to(lovable_dir)).replace("\\", "/")
        if any(rel.startswith(p) for p in SKIP_PREFIXES):
            continue
        if rel in covered:
            continue
        if "ui/" in rel and rel.endswith(("button.tsx", "input.tsx", "label.tsx")):
            continue
        domain = domain_from_path(rel)
        draft_name = f"{domain}-{Path(rel).stem.lower()}.draft.yml"
        draft_path = drafts_dir / draft_name
        content = draft_yaml(rel)
        draft_path.write_text(content, encoding="utf-8")
        missing.append({"uiFile": rel, "draftFile": str(draft_path.relative_to(artifacts_dir()))})

    report = {
        "ok": True,
        "dryRun": is_dry_run(),
        "humanInTheLoop": True,
        "uiFilesScanned": len(ui_files),
        "rulesSourcesKnown": len(covered),
        "missingRules": len(missing),
        "drafts": missing,
        "note": "Los borradores NO se commitean automáticamente — diseñador aprueba en Lovable.",
    }
    write_report("rules-refinement-report.json", report)
    (artifacts_dir() / "rules-refinement-summary.md").write_text(
        "# Borradores reglasActuacion propuestos\n\n"
        + "\n".join(f"- `{m['uiFile']}` → `{m['draftFile']}`" for m in missing)
        or "Sin gaps — toda la UI tiene regla asociada.",
        encoding="utf-8",
    )
    gh_output("rules_refinement_drafts", str(len(missing)))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
