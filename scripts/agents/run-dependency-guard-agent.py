#!/usr/bin/env python3
"""Agente 5 — dependency-guard: valida package.json, imports y dependencias nuevas."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENTS_DIR.parent / "lovable-sync"))
sys.path.insert(0, str(AGENTS_DIR))

from dsf_shared import load_manifest, load_yaml, norm_path, save_json
from agent_base import artifacts_dir, gh_output, write_report

IMPORT_RE = re.compile(r'''from\s+['"]([^./][^'"]+)['"]|import\s+['"]([^./][^'"]+)['"]''')

# Alias de paths del proyecto Lovable/WEB — no son paquetes npm.
PATH_ALIAS_PREFIXES = ("@/", "@lovable/", "@doevents/")


def is_path_alias(module: str) -> bool:
    return any(module.startswith(p) for p in PATH_ALIAS_PREFIXES)


def scan_imports(root: Path, ui_paths: list[str]) -> list[str]:
    packages: set[str] = set()
    for rel in ui_paths:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in IMPORT_RE.finditer(text):
            pkg = m.group(1) or m.group(2)
            if not pkg or is_path_alias(pkg):
                continue
            if pkg and not pkg.startswith("@"):
                packages.add(pkg.split("/")[0])
            elif pkg and pkg.startswith("@"):
                parts = pkg.split("/")
                packages.add("/".join(parts[:2]) if len(parts) > 1 else parts[0])
    return sorted(packages)


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF dependency-guard")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--change-manifest", required=True)
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    lovable = Path(args.lovable_dir).resolve()
    manifest = load_manifest(Path(args.change_manifest))
    policy = load_yaml(lovable / "reglasCalidad" / "dependency-policy.yml")

    changed = [norm_path(f.get("path", "")) for f in manifest.get("changedFiles", []) if f.get("path")]
    package_changed = any(p.endswith("package.json") or p.endswith("package-lock.json") for p in changed)
    ui_paths = [p for p in changed if p.startswith("src/")]
    external_imports = scan_imports(lovable, ui_paths)

    known_deps: set[str] = set()
    pkg_json = lovable / "package.json"
    if pkg_json.is_file():
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            known_deps.update((pkg.get(key) or {}).keys())

    new_deps = [d for d in external_imports if d not in known_deps and not d.startswith("react")]
    blocked = package_changed or bool(new_deps)

    result = {
        "runId": args.run_id,
        "packageJsonChanged": package_changed,
        "newDependencies": new_deps,
        "externalImportsScanned": external_imports,
        "riskLevel": "high" if blocked else "low",
        "agentTier": "manual" if blocked else "python",
        "requiresManualReview": blocked,
        "policy": policy.get("dependencyPolicy", {}),
    }

    out = artifacts_dir(args.run_id) / f"dependency-guard-{args.run_id}.json"
    save_json(out, result)
    write_report(f"dependency-guard-{args.run_id}.json", result, args.run_id)
    gh_output("dependency_blocked", str(blocked).lower())
    print(json.dumps({"ok": not blocked, "packageChanged": package_changed, "newDeps": new_deps}, indent=2))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
