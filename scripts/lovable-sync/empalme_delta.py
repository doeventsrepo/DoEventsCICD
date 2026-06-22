"""Empalme delta-only: aplica solo hunks Lovable sobre archivos WEB existentes."""
from __future__ import annotations

import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

BRIDGE_IMPORT_MARKERS = ("@doevents/shared", "lovable-bridge", "api-dev.doeventsapp")
WEB_BRIDGE_SYMBOLS = re.compile(
    r"\b(StoryAvatar|useActiveStoryAuthors|onOpenStory|LovablePostCardBridge)\b"
)


@dataclass
class DeltaApplyResult:
    web_text: str
    applied_ops: int = 0
    missed: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)


def git_file_at(root: Path, rev: str, rel_path: str) -> str | None:
    """Lee contenido de un archivo en una revisión git del repo Lovable."""
    if not rev or not rel_path:
        return None
    try:
        return subprocess.check_output(
            ["git", "show", f"{rev}:{rel_path.replace(chr(92), '/')}"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _attrs_added(old_block: str, new_block: str) -> list[str]:
    old_names = set(re.findall(r"([\w-]+)=", old_block))
    return [name for name in re.findall(r"([\w-]+)=", new_block) if name not in old_names]


def _change_already_in_web(web: str, old_block: str, new_block: str) -> bool:
    """True si WEB ya contiene el cambio del diff Lovable (p. ej. idempotencia CI)."""
    if new_block in web:
        return True
    if old_block in web:
        return False
    old_stripped = old_block.strip()
    if not old_stripped.startswith("<"):
        return False
    old_open = old_stripped.rstrip(">").strip()
    added_attrs = _attrs_added(old_block, new_block)
    for ln in web.splitlines():
        stripped = ln.strip()
        if not stripped.startswith(old_open.split()[0]):
            continue
        if not stripped.startswith(old_open) and old_open not in stripped:
            continue
        if added_attrs and all(re.search(rf"{re.escape(name)}\s*=", ln) for name in added_attrs):
            return True
    return False


def _find_unique_block(web: str, old_block: str) -> tuple[int, int] | None:
    """Busca bloque old_block en web; devuelve (start, end) si hay match único."""
    if not old_block:
        return None
    count = web.count(old_block)
    if count == 1:
        start = web.index(old_block)
        return start, start + len(old_block)
    if count > 1:
        return None
    # Fallback: match por líneas individuales si el bloque es una sola línea
    old_lines = old_block.splitlines()
    if len(old_lines) == 1:
        target = old_lines[0]
        web_lines = web.splitlines(keepends=True)
        hits = [i for i, ln in enumerate(web_lines) if ln.rstrip("\r\n") == target.rstrip("\r\n")]
        if len(hits) == 1:
            idx = hits[0]
            start = sum(len(web_lines[j]) for j in range(idx))
            end = start + len(web_lines[idx])
            return start, end
        if len(hits) > 1:
            return None
        # Match flexible de espacios
        norm_target = _normalize_ws(target)
        flex_hits = [
            i for i, ln in enumerate(web_lines)
            if _normalize_ws(ln) == norm_target
        ]
        if len(flex_hits) == 1:
            idx = flex_hits[0]
            start = sum(len(web_lines[j]) for j in range(idx))
            end = start + len(web_lines[idx])
            return start, end
    return None


def _try_tailwind_token_swap(web: str, old_line: str, new_line: str) -> str | None:
    """Si el diff Lovable solo cambia tokens de utilidad Tailwind, aplicar en WEB."""
    token_re = re.compile(r"(?:bg|text|border|ring|from|to|via)-(?:\[[^\]]+\]|[^\s`\"'{}]+)")
    old_tokens = set(token_re.findall(old_line))
    new_tokens = set(token_re.findall(new_line))
    removed = old_tokens - new_tokens
    added = new_tokens - old_tokens
    if len(removed) != 1 or len(added) != 1:
        return None
    old_tok, new_tok = removed.pop(), added.pop()
    if old_tok in new_line and old_tok not in removed:
        return None
    if web.count(old_tok) == 1:
        return web.replace(old_tok, new_tok, 1)
    return None


def _extract_ops(old: str, new: str) -> list[dict]:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            ops.append({"type": "replace", "old": old_lines[i1:i2], "new": new_lines[j1:j2]})
        elif tag == "insert":
            ops.append({
                "type": "insert",
                "new": new_lines[j1:j2],
                "anchor_before": old_lines[i1 - 1] if i1 > 0 else None,
                "anchor_after": old_lines[i1] if i1 < len(old_lines) else None,
            })
        elif tag == "delete":
            ops.append({"type": "delete", "old": old_lines[i1:i2]})
    return ops


def apply_lovable_delta(
    *,
    web_original: str,
    lovable_old: str,
    lovable_new: str,
    transform_fn: Callable[[str], str] | None = None,
) -> DeltaApplyResult:
    """Aplica el diff Lovable (old→new) sobre el archivo WEB existente."""
    if lovable_old == lovable_new:
        return DeltaApplyResult(web_text=web_original, applied_ops=0)

    web = web_original
    result = DeltaApplyResult(web_text=web_original)
    ops = _extract_ops(lovable_old, lovable_new)

    for op in ops:
        if op["type"] == "replace":
            old_block = "\n".join(op["old"])
            new_raw = "\n".join(op["new"])
            new_block = transform_fn(new_raw) if transform_fn else new_raw
            if old_block == new_block:
                continue
            span = _find_unique_block(web, old_block)
            if span is None:
                if _change_already_in_web(web, old_block, new_block):
                    continue
                if len(op["old"]) == 1 and len(op["new"]) == 1:
                    swapped = _try_tailwind_token_swap(web, op["old"][0], op["new"][0])
                    if swapped is not None:
                        web = swapped
                        result.applied_ops += 1
                        continue
                if web.count(old_block) > 1:
                    result.ambiguous.append(f"replace_ambiguo:{old_block[:60]}")
                else:
                    result.missed.append(f"replace_no_encontrado:{old_block[:60]}")
                continue
            start, end = span
            web = web[:start] + new_block + web[end:]
            result.applied_ops += 1

        elif op["type"] == "delete":
            old_block = "\n".join(op["old"])
            span = _find_unique_block(web, old_block)
            if span is None:
                result.missed.append(f"delete_no_encontrado:{old_block[:60]}")
                continue
            start, end = span
            web = web[:start] + web[end:]
            result.applied_ops += 1

        elif op["type"] == "insert":
            new_raw = "\n".join(op["new"])
            new_block = transform_fn(new_raw) if transform_fn else new_raw
            anchor = op.get("anchor_before") or op.get("anchor_after")
            if not anchor:
                result.missed.append(f"insert_sin_ancla:{new_raw[:60]}")
                continue
            span = _find_unique_block(web, anchor)
            if span is None:
                result.missed.append(f"insert_ancla_no_encontrada:{anchor[:60]}")
                continue
            start, end = span
            if op.get("anchor_before"):
                insert_at = end
                sep = "\n" if insert_at < len(web) and web[insert_at - 1 : insert_at] != "\n" else ""
                web = web[:insert_at] + sep + new_block + "\n" + web[insert_at:]
            else:
                insert_at = start
                web = web[:insert_at] + new_block + "\n" + web[insert_at:]
            result.applied_ops += 1

    result.web_text = web
    return result


def count_bridge_imports(text: str) -> int:
    count = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("import ") and any(m in line for m in BRIDGE_IMPORT_MARKERS):
            count += 1
    return count


def check_regression(
    web_before: str,
    web_after: str,
    lovable_old: str,
    lovable_new: str,
    config: dict | None = None,
) -> tuple[bool, list[str]]:
    """Detecta regresiones cuando el delta WEB excede el cambio Lovable."""
    cfg = config or {}
    violations: list[str] = []

    if cfg.get("requireBridgeMarkersPreserved", True):
        for marker in BRIDGE_IMPORT_MARKERS:
            if marker in web_before and marker not in web_after:
                violations.append(f"perdido_marcador:{marker}")
        before_imp = count_bridge_imports(web_before)
        after_imp = count_bridge_imports(web_after)
        if after_imp < before_imp:
            violations.append(f"imports_bridge_reducidos:{before_imp}->{after_imp}")

    for sym in set(WEB_BRIDGE_SYMBOLS.findall(web_before)):
        if sym not in web_after:
            violations.append(f"simbolo_web_perdido:{sym}")

    lovable_delta = abs(len(lovable_new.splitlines()) - len(lovable_old.splitlines()))
    web_delta = abs(len(web_after.splitlines()) - len(web_before.splitlines()))
    max_mult = float(cfg.get("maxWebLineDeltaMultiplier", 3))
    max_abs = int(cfg.get("maxAbsoluteWebLineDelta", 30))
    allowed = max(int(lovable_delta * max_mult), 5)
    if web_delta > max(max_abs, allowed) and lovable_delta <= 20:
        violations.append(
            f"delta_web_excesivo:lovable={lovable_delta},web={web_delta},max={max(max_abs, allowed)}"
        )

    if web_before.strip() == web_after.strip() and lovable_old.strip() != lovable_new.strip():
        # Permitir si el cambio Lovable ya estaba presente en WEB (idempotencia)
        ops = _extract_ops(lovable_old, lovable_new)
        pending = False
        for op in ops:
            if op["type"] == "replace":
                old_block = "\n".join(op["old"])
                new_block = "\n".join(op["new"])
                if not _change_already_in_web(web_after, old_block, new_block):
                    pending = True
            elif op["type"] in ("insert", "delete"):
                pending = True
        if pending:
            violations.append("sin_cambio_en_web_pese_a_diff_lovable")

    return len(violations) == 0, violations


def load_anti_regression_config(cicd_root: Path | None = None) -> dict:
    """Carga umbrales anti-regresión desde cicd.config.json."""
    root = cicd_root or Path(__file__).resolve().parents[2]
    cfg_path = root / "cicd.config.json"
    if not cfg_path.is_file():
        return {}
    try:
        import json

        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        strategy = (data.get("dsf") or {}).get("empalmeStrategy") or {}
        return strategy.get("antiRegression") or {}
    except Exception:
        return {}
