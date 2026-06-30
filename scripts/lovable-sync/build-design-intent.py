#!/usr/bin/env python3
"""Design Change Record (DCR) — intención del cambio Lovable para empalme y Cursor."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

NOISE = re.compile(r"^(changes?|fix|update|wip|merge|sync)$", re.I)
FEED_HINTS = re.compile(
    r"feed|hero|banner|tema|color|servicio|evento|historia|story|layout|secci[oó]n",
    re.I,
)


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: build-design-intent.py <lovable_dir> <manifest.json> [output.json]", file=sys.stderr)
        return 1

    lovable = Path(sys.argv[1]).resolve()
    manifest_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else manifest_path.parent / "design-intent.json"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = manifest.get("before") or "HEAD~1"
    after = manifest.get("after") or manifest.get("lovableSha") or "HEAD"

    messages: list[str] = []
    try:
        log = git(["log", f"{before}..{after}", "--format=%s"], lovable)
        messages = [ln.strip() for ln in log.splitlines() if ln.strip()]
    except subprocess.CalledProcessError:
        try:
            messages = [git(["log", "-1", "--format=%s", after], lovable)]
        except subprocess.CalledProcessError:
            messages = []

    meaningful = [m for m in messages if m and not NOISE.match(m.strip())]
    user_prompt = meaningful[0] if meaningful else (messages[0] if messages else "")

    ui_paths = [
        str(f.get("path") or "")
        for f in manifest.get("changedFiles") or []
        if f.get("kind") == "ui"
    ]
    layers: list[str] = []
    if any(p.endswith(".css") for p in ui_paths):
        layers.append("diseno.tokens")
    if any("/pages/" in p for p in ui_paths):
        layers.append("layout.page")
    if any("/components/feed/" in p for p in ui_paths):
        layers.append("diseno.feed")
    if manifest.get("hasRulesChanges"):
        layers.append("reglas")

    acceptance: list[str] = []
    combined = " ".join(meaningful + ui_paths)
    if FEED_HINTS.search(combined):
        acceptance.append("Feed WEB debe reflejar cambios visuales del commit Lovable sin mocks en páginas bridge.")
    if any("FeedHero" in p for p in ui_paths):
        acceptance.append("FeedHero conserva bridge @doevents/shared / historias API.")
    if any("Index.tsx" in p for p in ui_paths):
        acceptance.append("Cambios de Index.tsx se aplican en SocialWallTab (compareMode bridge), no full_sync.")

    if not user_prompt and ui_paths:
        user_prompt = f"Cambios UI: {', '.join(ui_paths[:5])}"

    dcr = {
        "lovableSha": manifest.get("lovableSha") or after,
        "before": before,
        "after": after,
        "userPrompt": user_prompt,
        "commitMessages": messages,
        "meaningfulMessages": meaningful,
        "uiPathsChanged": ui_paths,
        "layersChanged": layers,
        "acceptanceCriteria": acceptance,
        "rulesOnlyPush": bool(manifest.get("hasRulesChanges") and not manifest.get("hasUiChanges")),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dcr, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest["designIntent"] = dcr
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "userPrompt": user_prompt, "out": str(out_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
