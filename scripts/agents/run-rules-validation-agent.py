#!/usr/bin/env python3
"""Agente validación reglas — detecta YAML mal formados y sugiere correcciones."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Instalar PyYAML", file=sys.stderr)
    sys.exit(1)

_lovable_sync = Path(__file__).resolve().parents[1] / "lovable-sync"
sys.path.insert(0, str(_lovable_sync))
import importlib.util

_spec = importlib.util.spec_from_file_location("validate_rules", _lovable_sync / "validate-rules.py")
_vr = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_vr)
validate_file = _vr.validate_file

from agent_base import artifacts_dir, gh_output, is_dry_run, write_report


REQUIRED_FIELDS = {"id", "domain", "version", "description"}
RECOMMENDED_FIELDS = {"source", "metadata"}


def suggest_fix(path: Path, data: dict | None, errors: list[str], warnings: list[str]) -> list[str]:
    suggestions: list[str] = []
    stem = path.stem.replace("-", ".")
    if data is None:
        suggestions.append(f"Añadir cabecera YAML válida con id, domain, version, description en {path.name}")
        return suggestions
    if "id" not in data:
        suggestions.append(f'id: "{stem}"')
    if "domain" not in data:
        parent = path.parent.name
        suggestions.append(f'domain: {parent if parent != "reglasActuacion" else "general"}')
    if "version" not in data:
        suggestions.append('version: "1.0.0"')
    if "description" not in data and "descripcion" not in data:
        suggestions.append(f"description: >\n  Regla funcional para {path.stem}")
    if not any(k in data for k in ("source", "campos", "ui", "acciones")):
        suggestions.append("source:\n  - src/...  # componente que implementa esta regla")
    for w in warnings:
        if "pseudo-codigo" in w:
            suggestions.append("Reformatear YAML: evitar bloques de pseudo-código sin estructura clave-valor")
    return suggestions


def scan_dir(rules_dir: Path) -> dict:
    files = sorted(rules_dir.rglob("*.yml")) + sorted(rules_dir.rglob("*.yaml"))
    items: list[dict] = []
    for f in files:
        if f.name == "README.md":
            continue
        errs, warns = validate_file(f)
        data = None
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except Exception:
            pass
        suggestions = suggest_fix(f, data if isinstance(data, dict) else None, errs, warns)
        items.append(
            {
                "file": str(f.relative_to(rules_dir)),
                "errors": errs,
                "warnings": warns,
                "suggestions": suggestions,
                "ok": len(errs) == 0 and len([w for w in warns if "pseudo-codigo" in w]) == 0,
            }
        )
    return {
        "directory": str(rules_dir),
        "totalFiles": len(items),
        "okCount": sum(1 for i in items if i["ok"]),
        "needsFix": sum(1 for i in items if not i["ok"]),
        "items": items,
    }


def build_markdown(report: dict) -> str:
    lines = ["# Sugerencias de corrección — reglasActuacion/reglasDiseno", ""]
    for item in report["items"]:
        if item["ok"]:
            continue
        lines.append(f"## {item['file']}")
        for s in item["suggestions"]:
            lines.append(f"- {s}")
        lines.append("")
    return "\n".join(lines) if len(lines) > 2 else "# Sin correcciones pendientes\n"


def main() -> int:
    lovable_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LOVABLE_DIR", "."))

    reports: list[dict] = []
    for sub in ("reglasActuacion", "reglasDiseno"):
        d = lovable_dir / sub
        if d.exists():
            reports.append(scan_dir(d))

    combined = {
        "ok": all(r["needsFix"] == 0 for r in reports),
        "dryRun": is_dry_run(),
        "reports": reports,
    }
    out_dir = artifacts_dir()
    write_report("rules-validation-report.json", combined)
    md = build_markdown({"items": [i for r in reports for i in r["items"]]})
    (out_dir / "rules-fix-suggestions.md").write_text(md, encoding="utf-8")

    gh_output("rules_validation_ok", str(combined["ok"]).lower())
    print(json.dumps({"ok": combined["ok"], "needsFix": sum(r["needsFix"] for r in reports)}, indent=2))
    # No bloqueante: sugiere correcciones; CI continúa
    return 0


if __name__ == "__main__":
    sys.exit(main())
