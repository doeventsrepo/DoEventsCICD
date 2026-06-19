#!/usr/bin/env python3
"""Dry-run del agente Cursor: valida payload sin llamar API."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts" / "lovable-sync"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from reglas_paths import min_reglas_front_bytes, operativas_paths

AGENT_DIR = "ReglasAgente"
MIN_RULES_BYTES = min_reglas_front_bytes()


def read_optional(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    cicd_dir = Path(os.environ.get("CICD_DIR", ".")).resolve()
    lovable_dir = Path(os.environ.get("LOVABLE_DIR", ".")).resolve()
    web_dir = Path(os.environ.get("WEB_DIR", ".")).resolve()

    errors: list[str] = []
    checks: list[dict] = []

    rules_path = web_dir / AGENT_DIR / "reglas-front.md"
    rules_content = read_optional(rules_path)
    ok_rules = len(rules_content.strip()) >= MIN_RULES_BYTES
    checks.append({"check": "reglas-front.md", "ok": ok_rules, "bytes": len(rules_content)})
    if not ok_rules:
        errors.append(f"reglas-front.md insuficiente ({len(rules_content)} bytes)")

    ops = operativas_paths(cicd_dir)
    for key, path in ops.items():
        ok = path.exists() and path.stat().st_size > 100
        checks.append({"check": f"reglas:{key}", "ok": ok, "bytes": path.stat().st_size if path.exists() else 0})
        if not ok:
            errors.append(f"Falta Reglas operativa {key}: {path.name}")

    manifest_path = lovable_dir / "lovable-change-manifest.json"
    if not manifest_path.exists():
        manifest_path = Path(os.environ.get("MANIFEST_PATH", ""))
    manifest_raw = read_optional(manifest_path) if manifest_path else "{}"
    try:
        manifest = json.loads(manifest_raw or "{}")
        checks.append({"check": "manifest_json", "ok": True, "requiresAgent": manifest.get("requiresAgent")})
    except json.JSONDecodeError:
        manifest = {}
        checks.append({"check": "manifest_json", "ok": False})
        errors.append("Manifiesto JSON invalido")

    instructions = read_optional(ops["promptEmpalme"])
    reglas_doc = read_optional(ops["reglamento"])
    context = read_optional(lovable_dir / ".ai" / "agent-sync-context.md")

    payload_text_len = len(instructions) + len(reglas_doc) + len(rules_content) + len(context) + len(manifest_raw)
    checks.append({"check": "payload_size_chars", "ok": payload_text_len > 2000, "chars": payload_text_len})

    web_ref = os.environ.get("WEB_STARTING_REF", "feature/cicd/dev-automation")
    back_ref = os.environ.get("BACK_STARTING_REF", "feature/cicd/dev-automation")
    repos = [
        {"url": "https://github.com/doeventsrepo/DoEventsWEB", "startingRef": web_ref},
    ]
    if os.environ.get("AGENT_INCLUDE_BACK", "true").lower() == "true":
        repos.append({"url": "https://github.com/doeventsrepo/DoEventsBack", "startingRef": back_ref})

    lovable_sha = manifest.get("lovableSha", "sim-unknown")
    payload = {
        "prompt": {"text": "[DRY-RUN truncated]"},
        "model": {"id": os.environ.get("CURSOR_AGENT_MODEL", "composer-2.5")},
        "repos": repos,
        "target": {
            "autoCreatePr": False,
            "branchName": "feature/cicd/dev-automation",
        },
    }

    out_dir = Path(os.environ.get("SIM_OUTPUT_DIR", "output/agent-dry-run"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "payload-preview.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")

    preview = f"{instructions[:800]}\n...\n{reglas_doc[:400]}\n...\n"
    (out_dir / "prompt-preview.txt").write_text(preview, encoding="utf-8")

    print(json.dumps({"ok": len(errors) == 0, "errors": errors, "checks": checks}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
