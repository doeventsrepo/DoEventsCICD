#!/usr/bin/env python3
"""Agente revisión pre-merge — checklist anti-mocks, similitud, reglas-front, decision-log."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lovable-sync"))
from reglas_paths import min_reglas_front_bytes  # noqa: E402

from agent_base import artifacts_dir, cicd_root, gh_output, is_dry_run, write_report

MOCK_PATTERNS = ("mockEvents", "mockTickets", "mockOrders", "hardcodedEvents", "sampleData", "mockData")


def check_reglas_front(web_dir: Path) -> dict:
    path = web_dir / "ReglasAgente" / "reglas-front.md"
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    min_bytes = min_reglas_front_bytes(cicd_root())
    ok = len(content.strip()) >= min_bytes
    return {"check": "reglas-front.md", "ok": ok, "bytes": len(content), "minRequired": min_bytes}


def check_decision_log(web_dir: Path) -> dict:
    path = web_dir / "ReglasAgente" / "decision-log.md"
    ok = path.exists() and path.stat().st_size > 50
    return {"check": "decision-log.md", "ok": ok, "bytes": path.stat().st_size if path.exists() else 0}


def check_anti_mocks(web_dir: Path) -> dict:
    pages = web_dir / "packages" / "shell" / "src" / "pages"
    found: list[str] = []
    if pages.exists():
        for f in pages.rglob("*.tsx"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            for p in MOCK_PATTERNS:
                if p in text:
                    found.append(f"{f.name}:{p}")
    return {"check": "anti-mocks", "ok": len(found) == 0, "mocksFound": found[:20]}


def check_similarity(comparison_path: Path | None, target: float) -> dict:
    if not comparison_path or not comparison_path.exists():
        return {"check": "similarity", "ok": is_dry_run(), "percent": None, "target": target, "skipped": True}
    data = json.loads(comparison_path.read_text(encoding="utf-8"))
    pct = float(data.get("overallSimilarityPercent", 0))
    return {"check": "similarity", "ok": pct >= target or is_dry_run(), "percent": pct, "target": target}


def check_cambios_lovable(web_dir: Path) -> dict:
    path = web_dir / "ReglasAgente" / "cambios-lovable.json"
    ok = path.exists() and path.stat().st_size > 100
    return {"check": "cambios-lovable.json", "ok": ok}


def run_bash_anti_mocks(web_dir: Path) -> dict:
    script = cicd_root() / "scripts" / "lovable-sync" / "validate-no-mocks.sh"
    if not script.exists():
        return {"check": "validate-no-mocks.sh", "ok": True, "skipped": True}
    bash = next((p for p in [Path(r"C:\Program Files\Git\bin\bash.exe"), Path("/usr/bin/bash")] if p.exists()), None)
    if not bash:
        return {"check": "validate-no-mocks.sh", "ok": True, "skipped": True}
    proc = subprocess.run([str(bash), str(script), str(web_dir)], capture_output=True, text=True)
    return {"check": "validate-no-mocks.sh", "ok": proc.returncode == 0, "stderr": proc.stderr[:300]}


def main() -> int:
    web_dir = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEB_DIR", "."))
    comparison_arg = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("DESIGN_COMPARISON", "")
    comparison = Path(comparison_arg) if comparison_arg and comparison_arg not in (".", "") else None
    target = float(os.environ.get("DSF_TARGET_SIM", "98"))

    checks = [
        check_reglas_front(web_dir),
        check_decision_log(web_dir),
        check_cambios_lovable(web_dir),
        check_anti_mocks(web_dir),
        run_bash_anti_mocks(web_dir),
        check_similarity(comparison if comparison and comparison.exists() else None, target),
    ]
    ok = all(c.get("ok") or c.get("skipped") for c in checks)
    report = {"ok": ok, "dryRun": is_dry_run(), "checks": checks, "verdict": "APPROVE" if ok else "NEEDS_FIX"}
    write_report("premerge-review.json", report)
    gh_output("premerge_ok", str(ok).lower())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if ok or is_dry_run() else 1


if __name__ == "__main__":
    sys.exit(main())
