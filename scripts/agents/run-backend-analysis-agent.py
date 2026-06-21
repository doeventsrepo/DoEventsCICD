#!/usr/bin/env python3
"""Agente análisis backend — genera issues GitHub desde impacto-backend.md (sin modificar código)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from agent_base import artifacts_dir, gh_output, is_dry_run, is_local_mode, load_config, write_report

BACKEND_REQUIRED_RE = re.compile(
    r"(?P<title>.+?)\s*\|\s*(?P<motivo>.+?)\s*\|\s*(?P<prioridad>Alta|Media|Baja)",
    re.IGNORECASE,
)
ISSUE_SECTION_RE = re.compile(r"##\s*Backend pendiente|##\s*Gaps BACKEND", re.I)


def parse_impacto_backend(path: Path) -> list[dict]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    items: list[dict] = []
    in_table = False
    for line in text.splitlines():
        if "| Gap |" in line or "| Feature |" in line:
            in_table = True
            continue
        if in_table and line.strip().startswith("|") and "---" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 2 and cols[0].lower() not in ("gap", "feature"):
                items.append(
                    {
                        "title": cols[0],
                        "reason": cols[1] if len(cols) > 1 else "",
                        "priority": cols[2] if len(cols) > 2 else "Media",
                    }
                )
        elif in_table and line.strip() == "":
            in_table = False
    return items


def openapi_stub(item: dict) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")[:40]
    return f"""```yaml
# Borrador OpenAPI sugerido — requiere aprobación humana
paths:
  /api/v1/{slug}:
    post:
      summary: {item['title']}
      description: {item.get('reason', 'Pendiente definición')}
      tags: [backend-required]
      responses:
        '200':
          description: OK
        '501':
          description: Not implemented — issue DSF auto
```"""


def create_issue_gh(repo: str, item: dict, labels: list[str]) -> dict:
    body = f"""## Contexto DSF — BACKEND_REQUIRED

**Motivo:** {item.get('reason', 'N/A')}
**Prioridad:** {item.get('priority', 'Media')}

## Contrato sugerido (borrador)

{openapi_stub(item)}

---
*Generado por run-backend-analysis-agent.py — NO modifica código automáticamente.*
*Aprobación humana requerida antes de implementar.*
"""
    if is_dry_run() or is_local_mode():
        return {"dryRun": True, "title": item["title"], "repo": repo, "labels": labels}

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or os.environ.get("DOEVENTS_WEB_PAT")
    if not token:
        return {"skipped": True, "reason": "sin GH_TOKEN", "title": item["title"]}

    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", f"[BACKEND_REQUIRED] {item['title']}",
        "--body", body,
        "--label", ",".join(labels),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env={**os.environ, "GH_TOKEN": token})
        return {"ok": proc.returncode == 0, "url": proc.stdout.strip(), "stderr": proc.stderr[:500]}
    except FileNotFoundError:
        return {"skipped": True, "reason": "gh CLI no instalado", "title": item["title"]}


def main() -> int:
    web_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEB_DIR", "."))
    cfg = load_config()
    backend_repo = cfg.get("repositories", {}).get("backend", "doeventsrepo/DoEventsBack")
    impacto = web_dir / "ReglasAgente" / "impacto-backend.md"
    items = parse_impacto_backend(impacto)

    results: list[dict] = []
    labels = ["backend-required", "dsf-auto", "needs-human-approval"]
    for item in items:
        results.append(create_issue_gh(backend_repo, item, labels))

    report = {
        "ok": True,
        "dryRun": is_dry_run() or is_local_mode(),
        "backendRepo": backend_repo,
        "itemsFound": len(items),
        "issues": results,
        "humanApprovalRequired": True,
    }
    write_report("backend-analysis-report.json", report)
    gh_output("backend_issues_count", str(len(items)))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
