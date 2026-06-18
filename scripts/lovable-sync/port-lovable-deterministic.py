#!/usr/bin/env python3
"""Copia archivos Lovable (src/, public/) a DoEventsWEB."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_SRC_PREFIX = "packages/shell/src/lovable/"
DEFAULT_PUBLIC_PREFIX = "packages/shell/public/"
DEFAULT_RULES_PREFIX = "reglasActuacion/"
PORTABLE_PREFIXES = ("src/", "public/", "reglasActuacion/")
GIT_DIFF_PATHS = ("src/", "public/", "reglasActuacion/")
SYNC_SHA_RE = re.compile(r"\[lovable:([0-9a-f]{7,40})\]", re.I)


def map_path(rel: str, mapping: list[dict]) -> str | None:
    for m in mapping:
        src = m["lovable"]
        if rel.startswith(src):
            return rel.replace(src, m["web"], 1)
    if rel.startswith("src/"):
        return DEFAULT_SRC_PREFIX + rel[len("src/") :]
    if rel.startswith("public/"):
        return DEFAULT_PUBLIC_PREFIX + rel[len("public/") :]
    if rel.startswith("reglasActuacion/"):
        return DEFAULT_RULES_PREFIX + rel[len("reglasActuacion/") :]
    return None


def is_forbidden(rel: str, forbidden: list[str]) -> bool:
    return any(rel.startswith(p) or rel == p.rstrip("/") for p in forbidden)


def is_agent_registry(rel: str, registry: list[str]) -> bool:
    return rel in registry or any(rel.endswith("/" + r.split("/")[-1]) for r in registry)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_changed_files(lovable: Path, before: str, after: str) -> list[str]:
    out = subprocess.check_output(
        ["git", "diff", "--name-only", before, after, "--", *GIT_DIFF_PATHS],
        cwd=lovable,
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def last_synced_lovable_sha(web: Path) -> str | None:
    branch = os.environ.get("CICD_WEB_BRANCH", "feature/cicd/dev-automation")
    try:
        out = subprocess.check_output(
            [
                "git",
                "log",
                "-1",
                "--grep=lovable(sync)",
                "--format=%s",
                branch,
            ],
            cwd=web,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        return None
    if not out:
        return None
    match = SYNC_SHA_RE.search(out)
    return match.group(1) if match else None


def all_portable_files(lovable: Path, forbidden: list[str]) -> list[str]:
    files: list[str] = []
    for prefix in PORTABLE_PREFIXES:
        root = lovable / prefix.rstrip("/")
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                rel = path.relative_to(lovable).as_posix()
                if not is_forbidden(rel, forbidden):
                    files.append(rel)
    return sorted(files)


def copy_file(
    lovable: Path, web: Path, rel: str, mapping: list[dict], *, allow_overwrite: bool = False
) -> str | None:
    dest_rel = map_path(rel, mapping)
    if not dest_rel:
        return None
    src_file = lovable / rel
    dest_file = web / dest_rel
    if not src_file.exists():
        return None
    if dest_file.exists() and not allow_overwrite:
        return None
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest_file)
    return f"{rel} -> {dest_rel}"


def reconcile_missing_files(
    lovable: Path, web: Path, mapping: list[dict], forbidden: list[str], *, allow_overwrite: bool = False
) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []
    for rel in all_portable_files(lovable, forbidden):
        dest_rel = map_path(rel, mapping)
        if not dest_rel:
            skipped.append(rel)
            continue
        dest_file = web / dest_rel
        if dest_file.exists():
            continue
        result = copy_file(lovable, web, rel, mapping, allow_overwrite=allow_overwrite)
        if result:
            copied.append(result)
    return copied, skipped


def reconcile_all_files(
    lovable: Path, web: Path, mapping: list[dict], forbidden: list[str]
) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []
    for rel in all_portable_files(lovable, forbidden):
        dest_rel = map_path(rel, mapping)
        if not dest_rel:
            skipped.append(rel)
            continue
        src_file = lovable / rel
        dest_file = web / dest_rel
        if dest_file.exists() and file_hash(src_file) == file_hash(dest_file):
            continue
        result = copy_file(lovable, web, rel, mapping, allow_overwrite=allow_overwrite)
        if result:
            copied.append(result)
    return copied, skipped


def main() -> int:
    if len(sys.argv) < 4:
        print("Uso: port-lovable-deterministic.py <lovable_dir> <web_dir> <manifest.json>")
        return 1

    lovable = Path(sys.argv[1])
    web = Path(sys.argv[2])
    manifest_path = Path(sys.argv[3])
    mode = os.environ.get("LOVABLE_PORT_MODE", "").lower()
    allow_overwrite = os.environ.get("LOVABLE_PORT_OVERWRITE", "false").lower() == "true"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {"hasUiChanges": True, "changedFiles": []}

    port_map_path = web / ".lovable-port-map.json"
    port_map = json.loads(port_map_path.read_text(encoding="utf-8")) if port_map_path.exists() else {}
    mapping: list[dict] = port_map.get("pathMapping", [])
    registry: list[str] = port_map.get("agentRegistryFiles", [])
    forbidden: list[str] = port_map.get("forbiddenPaths", []) + [
        "src/integrations/",
        "src/main.tsx",
        "src/App.tsx",
        "src/test/",
        "src/vite-env.d.ts",
    ]

    manifest_mode = manifest.get("mode", "")
    if mode == "reconcile-full" or manifest_mode == "reconcile-full":
        print("AVISO: reconcile-full deshabilitado — no sobrescribir componentes adaptados", file=sys.stderr)
        copied, skipped = reconcile_missing_files(lovable, web, mapping, forbidden, allow_overwrite=allow_overwrite)
        print(f"Reconcile missing (sin overwrite): {len(copied)} archivo(s)")
    elif mode == "reconcile" or manifest_mode == "reconcile":
        copied, skipped = reconcile_missing_files(lovable, web, mapping, forbidden, allow_overwrite=allow_overwrite)
        print(f"Reconcile missing: {len(copied)} archivo(s) nuevo(s)")
    else:
        paths: list[str] = [x["path"] for x in manifest.get("changedFiles", []) if x.get("path")]
        if not paths:
            sha = manifest.get("lovableSha", "HEAD")
            before = manifest.get("before", "HEAD~5")
            paths = git_changed_files(lovable, before, sha)
            print(f"Fallback git diff {before}..{sha}: {len(paths)} archivo(s)")

        if not paths:
            last_sha = last_synced_lovable_sha(web)
            if last_sha:
                paths = git_changed_files(lovable, last_sha, "HEAD")
                print(f"Catch-up desde ultimo sync ({last_sha}): {len(paths)} archivo(s)")

        copied = []
        skipped = []
        for rel in paths:
            if is_forbidden(rel, forbidden):
                skipped.append(rel)
                continue
            dest_rel = map_path(rel, mapping)
            if dest_rel and dest_rel.replace("\\", "/") in registry:
                skipped.append(rel)
                continue
            result = copy_file(lovable, web, rel, mapping, allow_overwrite=allow_overwrite)
            if result:
                copied.append(result)
            else:
                skipped.append(rel)

        if not copied:
            copied, skipped = reconcile_missing_files(lovable, web, mapping, forbidden, allow_overwrite=allow_overwrite)
            print(f"Reconcile missing fallback: {len(copied)} archivo(s) nuevo(s)")

    print(json.dumps({"copied": copied, "skipped": skipped}, indent=2))
    if not copied:
        print("Sin archivos nuevos que portar (existentes protegidos contra overwrite)", file=sys.stderr)
        return 0
    if skipped:
        print(f"AVISO: {len(skipped)} archivo(s) sin mapear o excluido(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
