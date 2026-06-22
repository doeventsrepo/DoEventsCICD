"""Motor determinista de empalme Lovable → DoEventsWEB (sin Cursor API)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from design_normalize import strip_mock_blocks
from design_tokens import hardcoded_color_violations, load_design_tokens
from port_map_utils import is_excluded, load_port_map, load_port_map_data, map_lovable_to_web, mapping_for

AUTH_PREFIXES = (
    "src/pages/Login",
    "src/pages/SignUp",
    "src/pages/ForgotPassword",
    "src/pages/ResetPassword",
)
REEXPORT_MARKERS = ("export {", "export *", "export default")
BACKEND_HINTS = re.compile(
    r"supabase|stripe|paypal|kyc|banking|password.*reset|createUploadUrls",
    re.I,
)
BRIDGE_MARKERS = re.compile(r"lovable-bridge|@doevents/shared|useApi|api-dev\.doeventsapp", re.I)


@dataclass
class EmpalmeItem:
    lovable_path: str
    web_path: str
    similarity: float
    status: str
    tier: str
    reason: str
    applied: bool = False
    detail: str = ""


@dataclass
class EmpalmeResult:
    applied: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    cursor_required: list[dict[str, Any]] = field(default_factory=list)
    manual_required: list[dict[str, Any]] = field(default_factory=list)
    backend_required: list[dict[str, Any]] = field(default_factory=list)


def rewrite_imports(text: str) -> str:
    def repl_from(m: re.Match[str]) -> str:
        q, path = m.group(1), m.group(2)
        if path.startswith("@/"):
            path = "@lovable/" + path[2:]
        return f"from {q}{path}{q}"

    def repl_bare(m: re.Match[str]) -> str:
        q, path = m.group(1), m.group(2)
        if path.startswith("@/"):
            path = "@lovable/" + path[2:]
        return f"import {q}{path}{q}"

    text = re.sub(r'from (["\'])(@/[^"\']+)\1', repl_from, text)
    text = re.sub(r'import (["\'])(@/[^"\']+)\1', repl_bare, text)
    return text


def apply_token_fixes(text: str, tokens: dict[str, Any]) -> str:
    """Sustituciones seguras de colores hardcoded frecuentes por tokens semánticos."""
    if not tokens:
        return text
    replacements = [
        (r"\btext-white\b", "text-primary-foreground"),
        (r"\bbg-black\b", "bg-background"),
        (r"\btext-black\b", "text-foreground"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return text


def transform_lovable_source(text: str, *, tokens: dict[str, Any] | None = None, lovable_root: Path | None = None) -> str:
    text = strip_mock_blocks(text)
    text = re.sub(r"interface Mock(\w+)", r"interface \1Row", text)
    text = re.sub(r": Mock(\w+)", r": \1Row", text)
    text = re.sub(r"<Mock(\w+)", r"<\1Row", text)
    text = rewrite_imports(text)
    text = re.sub(r"import\s+\w+\s+from\s+['\"]@/assets/[^'\"]+['\"];\n?", "", text)
    text = apply_token_fixes(text, tokens or {})
    if lovable_root is not None:
        try:
            from quality_policy import apply_forbidden_fixes, load_quality_policy

            policy = load_quality_policy(lovable_root)
            text, _ = apply_forbidden_fixes(text, policy)
        except ImportError:
            pass
    return text


def is_reexport_stub(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    if not lines or len(lines) > 20:
        return False
    return all(any(m in ln for m in REEXPORT_MARKERS) for ln in lines)


def classify_tier(
    *,
    lovable_path: str,
    web_path: str,
    similarity: float,
    status: str,
    lovable_src: str,
    web_src: str,
    compare_mode: str,
    python_max_sim: float,
    force_paths: set[str] | None = None,
    force_diff_apply: bool = False,
    lovable_root: Path | None = None,
) -> tuple[str, str]:
    if any(lovable_path.startswith(p) for p in AUTH_PREFIXES) or compare_mode == "delegated":
        return "skipped", "auth_mfe_delegated"
    if "mfe-auth" in web_path.replace("\\", "/"):
        return "skipped", "auth_mfe_delegated"
    if is_reexport_stub(web_src):
        return "skipped", "bridge_reexport_preserved"

    if lovable_root is not None:
        try:
            from empalme_rules import resolve_agent_tier

            rule_info = resolve_agent_tier(lovable_path, lovable_root)
            layers = ",".join(rule_info.get("layers") or []) or "sin_capa"
            if rule_info.get("backendRequired"):
                return "backend", f"regla_yaml_backend ({layers})"
            rtier = rule_info.get("agentTier", "python")
            if rtier == "cursor":
                return "cursor", f"regla_yaml_cursor ({layers})"
            if rtier == "manual":
                return "manual", f"regla_yaml_manual ({layers})"
            if rtier == "skipped":
                return "skipped", "regla_yaml_delegated"
        except ImportError:
            pass

    if force_diff_apply and lovable_path in (force_paths or set()):
        if web_src and BRIDGE_MARKERS.search(web_src):
            return "python", "delta_only_archivo_empalado_con_bridge"
        if web_src:
            return "python", "delta_only_archivo_modificado_en_diff"
        return "python", "archivo_nuevo_en_diff"

    if BACKEND_HINTS.search(lovable_src) and similarity < 40:
        return "backend", "integracion_backend_requerida"
    if similarity >= python_max_sim and status == "minor_drift":
        return "manual", "ajuste_menor_manual_o_cursor_puntual"
    if similarity < 35 and web_src and BRIDGE_MARKERS.search(web_src):
        return "cursor", "logica_web_compleja_requiere_cursor"
    if similarity < 50 and len(lovable_src) > 8000:
        return "cursor", "componente_grande_requiere_cursor"
    if not web_src or status == "missing_in_web":
        return "python", "implementacion_determinista_nuevo_archivo"
    if similarity < python_max_sim:
        return "python", "empalme_determinista_sobre_archivo_existente"
    return "manual", "similitud_parcial_revisar_manual"


def resolve_targets(
    *,
    lovable_root: Path,
    web_root: Path,
    port_map_path: Path,
    comparison_files: list[dict] | None = None,
    changed_paths: list[str] | None = None,
    scope: str = "diff-only",
    python_max_sim: float = 85.0,
    max_items: int = 50,
) -> list[EmpalmeItem]:
    mapping = load_port_map(port_map_path)
    port_data = load_port_map_data(port_map_path)
    items: list[EmpalmeItem] = []

    if scope == "diff-only" and changed_paths:
        candidates = [p for p in changed_paths if p.startswith("src/") and not is_excluded(p, port_data)]
    elif comparison_files:
        candidates = []
        for entry in comparison_files:
            sim = float(entry.get("similarityPercent", 0))
            status = entry.get("status", "")
            if status == "aligned" or sim >= python_max_sim:
                continue
            candidates.append(entry.get("lovablePath", ""))
    else:
        candidates = []

    force_set = set(changed_paths or []) if scope == "diff-only" else set()
    seen: set[str] = set()
    for lovable_rel in candidates:
        if not lovable_rel or lovable_rel in seen:
            continue
        seen.add(lovable_rel)
        if is_excluded(lovable_rel, port_data):
            continue
        web_rel = map_lovable_to_web(lovable_rel, mapping)
        if not web_rel:
            items.append(
                EmpalmeItem(lovable_rel, "", 0.0, "unmapped", "manual", "sin_mapeo_en_port_map")
            )
            continue
        meta = mapping_for(lovable_rel, mapping) or {}
        compare_mode = meta.get("compareMode", "")
        lovable_path = lovable_root / lovable_rel
        web_path = web_root / web_rel
        if not lovable_path.is_file():
            continue
        lovable_src = lovable_path.read_text(encoding="utf-8", errors="replace")
        web_src = web_path.read_text(encoding="utf-8", errors="replace") if web_path.is_file() else ""
        entry = next((e for e in (comparison_files or []) if e.get("lovablePath") == lovable_rel), {})
        sim = float(entry.get("similarityPercent", 0))
        status = entry.get("status", "needs_adaptation" if sim < 85 else "minor_drift")

        if lovable_root is not None:
            try:
                from quality_policy import detect_escalations, is_delegated_path, load_quality_policy

                pol = load_quality_policy(lovable_root)
                if is_delegated_path(lovable_rel, pol):
                    items.append(EmpalmeItem(lovable_rel, web_rel, sim, status, "skipped", "reglasCalidad_delegated"))
                    continue
                esc = detect_escalations(lovable_src, lovable_rel, pol)
                if esc:
                    items.append(EmpalmeItem(
                        lovable_rel, web_rel, sim, status, "cursor",
                        f"reglasCalidad_escalate ({'; '.join(esc[:2])})",
                    ))
                    continue
            except ImportError:
                pass

        tier, reason = classify_tier(
            lovable_path=lovable_rel,
            web_path=web_rel,
            similarity=sim,
            status=status,
            lovable_src=lovable_src,
            web_src=web_src,
            compare_mode=compare_mode,
            python_max_sim=python_max_sim,
            force_paths=force_set,
            force_diff_apply=scope == "diff-only",
            lovable_root=lovable_root,
        )
        items.append(EmpalmeItem(lovable_rel, web_rel, sim, status, tier, reason))

    items.sort(key=lambda i: ({"python": 0, "cursor": 1, "manual": 2, "backend": 3, "skipped": 4}.get(i.tier, 9), i.similarity))
    return items[:max_items]


def run_empalme(
    *,
    lovable_root: Path,
    web_root: Path,
    port_map_path: Path,
    targets: list[EmpalmeItem],
    dry_run: bool = False,
    lovable_before_rev: str | None = None,
    lovable_after_rev: str | None = None,
    anti_regression: dict | None = None,
) -> EmpalmeResult:
    tokens = load_design_tokens(lovable_root)
    result = EmpalmeResult()

    for item in targets:
        base = {
            "lovablePath": item.lovable_path,
            "webPath": item.web_path,
            "similarityPercent": item.similarity,
            "status": item.status,
            "reason": item.reason,
        }
        if item.tier == "skipped":
            result.skipped.append({**base, "tier": "skipped"})
            continue
        if item.tier == "backend":
            result.backend_required.append({**base, "tier": "backend"})
            continue
        if item.tier == "cursor":
            result.cursor_required.append({**base, "tier": "cursor"})
            continue
        if item.tier == "manual":
            result.manual_required.append({**base, "tier": "manual"})
            continue

        lovable_path = lovable_root / item.lovable_path
        web_path = web_root / item.web_path
        if not lovable_path.is_file():
            result.skipped.append({**base, "tier": "skipped", "reason": "missing_lovable"})
            continue

        from empalme_delta import apply_lovable_delta, check_regression, git_file_at

        lovable_new_raw = (
            git_file_at(lovable_root, lovable_after_rev, item.lovable_path)
            if lovable_after_rev
            else None
        )
        if not lovable_new_raw:
            lovable_new_raw = lovable_path.read_text(encoding="utf-8", errors="replace")
        web_original = web_path.read_text(encoding="utf-8", errors="replace") if web_path.is_file() else ""
        apply_mode = "full"
        delta_detail = ""

        if web_original:
            apply_mode = "delta"
            lovable_old_raw = (
                git_file_at(lovable_root, lovable_before_rev, item.lovable_path)
                if lovable_before_rev
                else None
            )
            if not lovable_old_raw:
                result.cursor_required.append({
                    **base,
                    "tier": "cursor",
                    "reason": "sin_revision_lovable_anterior_para_delta",
                })
                continue

            def _transform_fragment(text: str) -> str:
                return transform_lovable_source(text, tokens=tokens, lovable_root=lovable_root)

            delta = apply_lovable_delta(
                web_original=web_original,
                lovable_old=lovable_old_raw,
                lovable_new=lovable_new_raw,
                transform_fn=_transform_fragment,
            )
            if delta.missed or delta.ambiguous:
                issues = delta.missed + delta.ambiguous
                result.cursor_required.append({
                    **base,
                    "tier": "cursor",
                    "reason": f"delta_incompleto ({'; '.join(issues[:3])})",
                })
                continue

            transformed = delta.web_text
            delta_detail = f"delta_ops={delta.applied_ops}"

            ok, violations = check_regression(
                web_original, transformed, lovable_old_raw, lovable_new_raw, anti_regression or {}
            )
            if not ok:
                result.cursor_required.append({
                    **base,
                    "tier": "cursor",
                    "reason": f"anti_regression ({'; '.join(violations[:3])})",
                })
                continue
        else:
            transformed = transform_lovable_source(
                lovable_new_raw,
                tokens=tokens,
                lovable_root=lovable_root,
            )

        if lovable_root is not None:
            try:
                from quality_policy import detect_escalations, load_quality_policy

                esc = detect_escalations(transformed, item.lovable_path, load_quality_policy(lovable_root))
                if esc:
                    result.cursor_required.append({**base, "tier": "cursor", "reason": "; ".join(esc[:3])})
                    continue
            except ImportError:
                pass

        hardcoded = hardcoded_color_violations(transformed)
        if dry_run:
            result.applied.append({
                **base,
                "tier": "python",
                "dryRun": True,
                "applyMode": apply_mode,
                "deltaDetail": delta_detail,
                "hardcodedRemaining": len(hardcoded),
            })
            continue

        web_path.parent.mkdir(parents=True, exist_ok=True)
        web_path.write_text(transformed, encoding="utf-8")
        result.applied.append({
            **base,
            "tier": "python",
            "applyMode": apply_mode,
            "deltaDetail": delta_detail,
            "bytes": len(transformed),
            "hardcodedRemaining": len(hardcoded),
        })

    return result
