#!/usr/bin/env python3
"""
Simulación empalme DSF — sin Cursor API, sin loops, sin push.

Uso (desde DoEventsCICD):
  python simulation/scripts/run-empalme-simulation.py
  python simulation/scripts/run-empalme-simulation.py --apply   # escribe en sandbox WEB
  python simulation/scripts/run-empalme-simulation.py --file src/components/feed/FeedBanner.tsx
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = CICD_ROOT / "scripts" / "lovable-sync"
DEFAULT_LOVABLE = CICD_ROOT.parent / "discover-joyful-feed"
DEFAULT_WEB = CICD_ROOT.parent / "DoEventsWEB"
SANDBOX_WEB = CICD_ROOT / "simulation" / "sandbox" / "DoEventsWEB"


def run(cmd: list[str], env: dict | None = None) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, env={**os.environ, **(env or {})})


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulación empalme Python-first")
    parser.add_argument("--lovable-dir", default=str(DEFAULT_LOVABLE))
    parser.add_argument("--web-dir", default="")
    parser.add_argument("--apply", action="store_true", help="Aplicar en sandbox (no productivo)")
    parser.add_argument("--file", action="append", default=[], help="Simular cambio en ruta Lovable")
    parser.add_argument("--run-id", default=f"sim-{int(datetime.now().timestamp())}")
    args = parser.parse_args()

    web_dir = Path(args.web_dir) if args.web_dir else (SANDBOX_WEB if SANDBOX_WEB.is_dir() else DEFAULT_WEB)
    if not web_dir.is_dir():
        print(f"ERROR: WEB no encontrado: {web_dir}", file=sys.stderr)
        return 1

    lovable = Path(args.lovable_dir).resolve()
    port_map = web_dir / ".lovable-port-map.json"
    out_dir = CICD_ROOT / "artifacts" / "empalme-simulation" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out_dir / "lovable-change-manifest.json"
    if args.file:
        manifest = {
            "lovableSha": "simulated",
            "hasUiChanges": True,
            "changedFiles": [{"path": p, "kind": "ui", "status": "M"} for p in args.file],
        }
    else:
        manifest = {
            "lovableSha": "simulated-all",
            "hasUiChanges": True,
            "changedFiles": [
                {"path": "src/components/feed/FeedBanner.tsx", "kind": "ui", "status": "M"},
            ],
        }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    os.environ["DSF_LOCAL_MODE"] = "1"
    dry = [] if args.apply else ["--dry-run"]

    rc = run([
        sys.executable, str(SCRIPTS / "empalme-orchestrator.py"),
        "--lovable-dir", str(lovable),
        "--web-dir", str(web_dir),
        "--cicd-dir", str(CICD_ROOT),
        "--port-map", str(port_map),
        "--change-manifest", str(manifest_path),
        "--run-id", args.run_id,
        *dry,
    ], env={"CICD_DIR": str(CICD_ROOT)})

    report_md = CICD_ROOT / "Reports" / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-empalme-{args.run_id}.md"
    if report_md.is_file():
        print(f"\nReporte: {report_md}")
    summary = CICD_ROOT / f"empalme-summary-{args.run_id}.json"
    if summary.is_file():
        print(json.dumps(json.loads(summary.read_text(encoding="utf-8")), indent=2))

    return rc


if __name__ == "__main__":
    sys.exit(main())
