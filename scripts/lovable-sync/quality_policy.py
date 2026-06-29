"""Política de calidad DSF — reglasCalidad/ → empalme y change-manifest."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_quality_policy(lovable_root: Path) -> dict[str, Any]:
    base = lovable_root / "reglasCalidad"
    return {
        "requiredChecks": _load(base / "required-checks.yml"),
        "forbiddenPatterns": _load(base / "forbidden-patterns.yml"),
        "riskPolicy": _load(base / "risk-policy.yml"),
        "rollbackPolicy": _load(base / "rollback-policy.yml"),
    }


def apply_forbidden_fixes(text: str, policy: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Aplica reemplazos seguros definidos en forbidden-patterns.yml."""
    fp = policy.get("forbiddenPatterns") or {}
    fixes: list[dict[str, Any]] = []
    for group in (fp.get("patterns") or {}).values():
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "replace")
            if action not in ("replace", "strip"):
                continue
            regex = item.get("regex")
            repl = item.get("replace", "")
            if not regex:
                continue
            if action == "strip" and "mockData" in str(regex):
                lines_out: list[str] = []
                for line in text.splitlines(keepends=True):
                    if line.lstrip().startswith("import ") and re.search(regex, line):
                        lines_out.append(line)
                    else:
                        lines_out.append(re.sub(regex, repl, line))
                text = "".join(lines_out)
                continue
            new_text, n = re.subn(regex, repl, text)
            if n:
                fixes.append({"regex": regex, "replace": repl, "count": n})
                text = new_text
    return text, fixes


def detect_escalations(text: str, lovable_path: str, policy: dict[str, Any]) -> list[str]:
    """Detecta patrones que requieren Cursor según reglasCalidad."""
    fp = policy.get("forbiddenPatterns") or {}
    reasons: list[str] = []
    rel = lovable_path.replace("\\", "/")

    for p in fp.get("cursorOnlyPaths") or []:
        if rel.startswith(p) or p.rstrip("/") in rel:
            reasons.append(f"cursorOnlyPath:{p}")

    for group in (fp.get("patterns") or {}).values():
        if not isinstance(group, list):
            continue
        for item in group:
            if item.get("action") == "escalate" and item.get("regex"):
                if re.search(item["regex"], text):
                    reasons.append(item.get("note") or item["regex"])

    arch = (fp.get("patterns") or {}).get("architecture") or []
    for item in arch:
        paths = item.get("paths") or []
        if any(rel.startswith(p) for p in paths):
            if item.get("action") == "escalate":
                reasons.append(item.get("pattern", "architecture_escalate"))

    return reasons


def is_delegated_path(lovable_path: str, policy: dict[str, Any]) -> bool:
    fp = policy.get("forbiddenPatterns") or {}
    rel = lovable_path.replace("\\", "/")
    return any(rel.startswith(p) or rel == p for p in fp.get("delegatedPaths") or [])


def cursor_policy(policy: dict[str, Any]) -> dict[str, Any]:
    rp = policy.get("riskPolicy") or {}
    return rp.get("cursorPolicy") or {}


def compute_risk_level(
    *,
    layers: list[str],
    agent_tier: str,
    blocked: bool = False,
    backend_required: bool = False,
) -> str:
    if blocked:
        return "blocked"
    if backend_required or agent_tier == "backend":
        return "high"
    if agent_tier == "cursor" or "logica" in layers:
        return "high"
    if any(l in layers for l in ("formulario", "campos", "navegacion")):
        return "medium"
    return "low"


def preserve_bridge_lines(web_text: str) -> list[str]:
    """Extrae imports críticos del WEB existente que Python debe preservar."""
    keep: list[str] = []
    markers = ("lovable-bridge", "@doevents/shared", "api-dev.doeventsapp")
    lines = web_text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        s = lines[i].strip()
        if s.startswith("import ") or s.startswith("export "):
            start = i
            j = i
            while j < n:
                if lines[j].rstrip().endswith(";"):
                    j += 1
                    break
                j += 1
            block = "\n".join(lines[start:j])
            if any(m in block for m in markers):
                keep.append(block)
            i = j
        else:
            i += 1
    return keep


def merge_preserve_bridge(lovable_transformed: str, web_original: str) -> str:
    """Inserta imports bridge del WEB si faltan en el empalme Python."""
    bridge_lines = preserve_bridge_lines(web_original)
    if not bridge_lines:
        return lovable_transformed
    out_lines = lovable_transformed.splitlines()
    existing_blocks = set(preserve_bridge_lines(lovable_transformed))
    prepend: list[str] = []
    for bl in bridge_lines:
        if bl not in existing_blocks and bl not in lovable_transformed:
            prepend.extend(bl.splitlines())
    if not prepend:
        return lovable_transformed
    # Insertar tras primer bloque de imports
    idx = 0
    for i, ln in enumerate(out_lines):
        if ln.strip().startswith("import ") or ln.strip().startswith("export "):
            idx = i + 1
        elif idx > 0 and ln.strip() and not ln.strip().startswith("//"):
            break
    merged = out_lines[:idx] + prepend + out_lines[idx:]
    return "\n".join(merged) + ("\n" if lovable_transformed.endswith("\n") else "")
