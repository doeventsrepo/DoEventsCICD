#!/usr/bin/env python3
"""Genera manifiesto JSON de cambios Lovable entre dos commits."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

WATCH_PREFIXES = (
    "src/",
    "public/",
    "reglasActuacion/",
    "tailwind.config.ts",
    "index.html",
)
SYNC_SHA_RE = re.compile(r"\[lovable:([0-9a-f]{7,40})\]", re.I)


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def rev_exists(cwd: Path, rev: str) -> bool:
    try:
        git(["rev-parse", "--verify", f"{rev}^{{commit}}"], cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def resolve_before(cwd: Path, before: str) -> str:
    if rev_exists(cwd, before):
        return before
    print(f"AVISO: revision {before} no existe en repo Lovable; usando raiz", file=sys.stderr)
    return git(["rev-list", "--max-parents=0", "HEAD"], cwd)


def last_synced_lovable_sha(web: Path) -> str | None:
    try:
        out = git(["log", "-1", "--grep=lovable(sync)", "--format=%s", "develop"], web)
    except subprocess.CalledProcessError:
        return None
    if not out:
        return None
    match = SYNC_SHA_RE.search(out)
    return match.group(1) if match else None


def classify(path: str) -> str:
    if path.startswith("reglasActuacion/"):
        return "rules"
    if path.startswith("src/") or path.startswith("public/"):
        return "ui"
    return "config"


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    before = sys.argv[2] if len(sys.argv) > 2 else "HEAD~1"
    after = sys.argv[3] if len(sys.argv) > 3 else "HEAD"
    web_dir = Path(sys.argv[4]) if len(sys.argv) > 4 else None
    mode = "diff"

    if before in ("__last_sync__", "workflow_dispatch") and web_dir and web_dir.exists():
        last_sha = last_synced_lovable_sha(web_dir)
        if last_sha and rev_exists(root, last_sha):
            before = last_sha
            print(f"Catch-up desde ultimo sync WEB: {last_sha}")
        else:
            before = resolve_before(root, before if before not in ("__last_sync__", "workflow_dispatch") else "HEAD~1")
            print(f"Sin sync previo valido; desde: {before}")
        mode = "catch-up"

    diff = git(["diff", "--name-status", before, after], root)
    files: list[dict] = []
    for line in diff.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1]
        if not any(path.startswith(p) or path == p.rstrip("/") for p in WATCH_PREFIXES):
            continue
        files.append({"status": status, "path": path, "kind": classify(path)})

    sha = git(["rev-parse", after], root)
    rules_changed = [f for f in files if f["kind"] == "rules"]
    ui_changed = [f for f in files if f["kind"] == "ui"]

    manifest = {
        "lovableSha": sha,
        "before": before,
        "after": after,
        "mode": mode,
        "changedFiles": files,
        "hasUiChanges": len(ui_changed) > 0,
        "hasRulesChanges": len(rules_changed) > 0,
        "changedRules": [f["path"] for f in rules_changed],
        "requiresAgent": len(rules_changed) > 0 or len(ui_changed) > 0,
    }
    out = root / "lovable-change-manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
