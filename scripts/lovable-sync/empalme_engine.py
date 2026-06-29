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
LOVABLE_SUPABASE = re.compile(r"integrations/supabase|supabase\.", re.I)


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
    text = re.sub(
        r"from\s+(['\"])@lovable/data/\1",
        r"from \1@lovable/data/mockData\1",
        text,
    )
    text = re.sub(
        r"^import\s+.*from\s+['\"]@(?:lovable/)?integrations/supabase/[^'\"]+['\"];\s*\n?",
        "",
        text,
        flags=re.M,
    )
    text = apply_token_fixes(text, tokens or {})
    if lovable_root is not None:
        try:
            from quality_policy import apply_forbidden_fixes, load_quality_policy

            policy = load_quality_policy(lovable_root)
            text, _ = apply_forbidden_fixes(text, policy)
        except ImportError:
            pass
    return text


def preserve_web_exports(web_original: str, transformed: str) -> str:
    """Conserva exports WEB (const/interface/type) que Lovable full-sync no incluye."""
    blocks: list[str] = []
    lines = web_original.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"export\s+(const|interface|type)\s+(\w+)", line.strip())
        if not m:
            i += 1
            continue
        kind, name = m.group(1), m.group(2)
        if name in transformed:
            i += 1
            continue
        block = [line]
        i += 1
        if kind == "interface" and "{" in line and "}" not in line.split("{", 1)[-1]:
            while i < len(lines):
                block.append(lines[i])
                if "}" in lines[i]:
                    i += 1
                    break
                i += 1
        elif kind == "type" and "{" in line and ";" not in line:
            while i < len(lines):
                block.append(lines[i])
                if ";" in lines[i]:
                    i += 1
                    break
                i += 1
        blocks.append("\n".join(block))
    if not blocks:
        return transformed
    lines_out = transformed.splitlines()
    insert_at = _leading_import_end(lines_out)
    merged = lines_out[:insert_at] + blocks + lines_out[insert_at:]
    return "\n".join(merged) + ("\n" if transformed.endswith("\n") else "")


def _leading_import_end(lines: list[str]) -> int:
    """Índice tras el bloque de imports al inicio del archivo."""
    i = 0
    n = len(lines)
    while i < n:
        st = lines[i].strip()
        if not st or st.startswith("//"):
            i += 1
            continue
        if not (st.startswith("import ") or (st.startswith("export ") and " from " in st)):
            break
        while i < n:
            if lines[i].rstrip().endswith(";"):
                i += 1
                break
            i += 1
    return i


def preserve_bridge_imports(web_original: str, transformed: str) -> str:
    """Reinserta imports bridge del WEB original si el full-sync los eliminó."""
    from empalme_delta import BRIDGE_IMPORT_MARKERS

    missing: list[str] = []
    for line in web_original.splitlines():
        s = line.strip()
        if not s.startswith("import "):
            continue
        if not any(m in line for m in BRIDGE_IMPORT_MARKERS):
            continue
        if line not in transformed:
            missing.append(line)
    if not missing:
        return transformed

    lines = transformed.splitlines()
    insert_at = _leading_import_end(lines)
    merged = lines[:insert_at] + missing + lines[insert_at:]
    return "\n".join(merged) + ("\n" if transformed.endswith("\n") else "")


def preserve_lovable_asset_imports(
    lovable_src: str,
    transformed: str,
    *,
    tokens: dict | None = None,
    lovable_root: Path | None = None,
) -> str:
    """Reinserta imports @lovable/assets del Lovable transformado si full-sync los perdió."""
    ref = transform_lovable_source(lovable_src, tokens=tokens, lovable_root=lovable_root)
    asset_lines: list[str] = []
    for line in ref.splitlines():
        s = line.strip()
        if s.startswith("import ") and "@lovable/assets/" in line and line not in transformed:
            asset_lines.append(line)
    if not asset_lines:
        return transformed
    lines = transformed.splitlines()
    insert_at = _leading_import_end(lines)
    merged = lines[:insert_at] + asset_lines + lines[insert_at:]
    return "\n".join(merged) + ("\n" if transformed.endswith("\n") else "")


def is_reexport_stub(text: str) -> bool:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("//")]
    if not lines or len(lines) > 20:
        return False
    return all(any(m in ln for m in REEXPORT_MARKERS) for ln in lines)


def python_fidelity_eligible(lovable_root: Path | None, lovable_path: str) -> bool:
    """Archivos tier python sin backend — empalme fiel vía Python, sin reinterpretar en Cursor."""
    if lovable_root is None:
        return False
    try:
        from empalme_rules import resolve_agent_tier

        info = resolve_agent_tier(lovable_path, lovable_root)
    except ImportError:
        return False
    if info.get("agentTier") != "python" or info.get("backendRequired"):
        return False
    heavy = {"backend", "seguridad"}
    if heavy.intersection(set(info.get("layers") or [])):
        return False
    return True


def fidelity_anti_regression(cfg: dict) -> dict:
    return {
        **cfg,
        "requireBridgeMarkersPreserved": True,
        "maxAbsoluteWebLineDelta": max(int(cfg.get("maxAbsoluteWebLineDelta", 30)), 1200),
        "maxWebLineDeltaMultiplier": max(float(cfg.get("maxWebLineDeltaMultiplier", 3)), 100),
        "blockOnUnappliedDelta": False,
    }


def merge_css_fidelity_web(web: str, lovable_old: str | None, lovable_new: str) -> str:
    """Aplica delta CSS; si falla, añade bloques nuevos de Lovable (p. ej. tokens feed)."""
    from empalme_delta import apply_lovable_delta

    old = lovable_old or web
    delta = apply_lovable_delta(
        web_original=web,
        lovable_old=old,
        lovable_new=lovable_new,
        transform_fn=lambda t: t,
    )
    if delta.applied_ops > 0 and not delta.ambiguous:
        return delta.web_text
    if "data-feed-theme" in lovable_new and "data-feed-theme" not in web:
        marker = "/* Feed Gold Theme"
        start = lovable_new.find(marker)
        if start < 0:
            start = lovable_new.find("html[data-feed-theme")
        if start >= 0:
            block = lovable_new[start:].strip()
            if block:
                return web.rstrip() + "\n\n" + block + "\n"
    added: list[str] = []
    old_set = set((lovable_old or "").splitlines())
    for ln in lovable_new.splitlines():
        s = ln.strip()
        if not s or ln in web or ln in old_set:
            continue
        if s.startswith("--") or s.startswith("html[") or s.startswith(".dark") or "feed-hero" in s:
            added.append(ln)
    if added:
        return web.rstrip() + "\n\n" + "\n".join(added) + "\n"
    return web


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

    # diff-only: aplicar delta git del manifiesto antes de reglas YAML (p. ej. SeatingMapEditor)
    if force_diff_apply and lovable_path in (force_paths or set()):
        if web_src and BRIDGE_MARKERS.search(web_src):
            return "python", "delta_only_archivo_empalado_con_bridge"
        if web_src:
            return "python", "delta_only_archivo_modificado_en_diff"
        return "python", "archivo_nuevo_en_diff"

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
    sync_mode: str = "auto",
    python_max_sim: float = 85.0,
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
        web_existed_before = web_path.is_file()
        web_original = web_path.read_text(encoding="utf-8", errors="replace") if web_existed_before else ""
        fidelity = python_fidelity_eligible(lovable_root, item.lovable_path)
        effective_mode = "auto" if fidelity or sync_mode == "auto" else sync_mode
        reg_cfg = fidelity_anti_regression(anti_regression or {}) if fidelity else dict(anti_regression or {})
        is_css = item.lovable_path.endswith(".css")
        apply_mode = "full"
        delta_detail = ""
        use_full = effective_mode == "full" or not web_original
        lovable_old_raw: str | None = None
        transformed = web_original
        fidelity_override = False

        if web_original and not use_full:
            apply_mode = "delta"
            lovable_old_raw = (
                git_file_at(lovable_root, lovable_before_rev, item.lovable_path)
                if lovable_before_rev
                else None
            )
            if not lovable_old_raw:
                if effective_mode == "auto" and (item.similarity < python_max_sim or fidelity):
                    use_full = True
                elif fidelity and is_css:
                    use_full = True
                else:
                    result.cursor_required.append({
                        **base,
                        "tier": "cursor",
                        "reason": "sin_revision_lovable_anterior_para_delta",
                    })
                    continue

            if not use_full:
                def _transform_fragment(text: str) -> str:
                    return transform_lovable_source(text, tokens=tokens, lovable_root=lovable_root)

                delta = apply_lovable_delta(
                    web_original=web_original,
                    lovable_old=lovable_old_raw,
                    lovable_new=lovable_new_raw,
                    transform_fn=_transform_fragment,
                )
                if delta.missed or delta.ambiguous:
                    partial_ok = (
                        delta.applied_ops > 0
                        and not delta.ambiguous
                        and all(m.startswith("insert_ancla_no_encontrada:") for m in delta.missed)
                    )
                    if partial_ok:
                        pass
                    elif effective_mode == "auto" and (item.similarity < python_max_sim or fidelity):
                        use_full = True
                    elif fidelity and is_css:
                        transformed = merge_css_fidelity_web(web_original, lovable_old_raw, lovable_new_raw)
                        apply_mode = "css_fidelity_merge"
                        delta_detail = "css_fidelity_merge"
                        use_full = False
                    else:
                        issues = delta.missed + delta.ambiguous
                        result.cursor_required.append({
                            **base,
                            "tier": "cursor",
                            "reason": f"delta_incompleto ({'; '.join(issues[:3])})",
                        })
                        continue

                if not use_full and apply_mode != "css_fidelity_merge":
                    transformed = delta.web_text
                    delta_detail = f"delta_ops={delta.applied_ops}"
                    if delta.applied_ops == 0 and effective_mode == "auto" and (item.similarity < python_max_sim or fidelity):
                        use_full = True
                    elif fidelity and is_css:
                        transformed = merge_css_fidelity_web(web_original, lovable_old_raw, lovable_new_raw)
                        apply_mode = "css_fidelity_merge"
                        delta_detail = "css_fidelity_merge"
                    else:
                        ok, violations = check_regression(
                            web_original, transformed, lovable_old_raw, lovable_new_raw, reg_cfg
                        )
                        if not ok:
                            if effective_mode == "auto" and (item.similarity < python_max_sim or fidelity):
                                use_full = True
                            elif fidelity:
                                fidelity_override = True
                            else:
                                result.cursor_required.append({
                                    **base,
                                    "tier": "cursor",
                                    "reason": f"anti_regression ({'; '.join(violations[:3])})",
                                })
                                continue

        if use_full and web_original and LOVABLE_SUPABASE.search(lovable_new_raw) and BRIDGE_MARKERS.search(web_original):
            if not fidelity:
                result.cursor_required.append({
                    **base,
                    "tier": "cursor",
                    "reason": "lovable_supabase_vs_web_bridge",
                })
                continue

        if (
            use_full
            and web_original
            and "/contexts/" in item.lovable_path.replace("\\", "/")
            and BRIDGE_MARKERS.search(web_original)
        ):
            if not fidelity:
                result.cursor_required.append({
                    **base,
                    "tier": "cursor",
                    "reason": "contexto_bridge_requiere_merge_manual",
                })
                continue

        if apply_mode == "css_fidelity_merge":
            pass
        elif use_full or not web_original:
            apply_mode = "full" if web_original else "full_new"
            transformed = transform_lovable_source(
                lovable_new_raw,
                tokens=tokens,
                lovable_root=lovable_root,
            )
            if web_original and is_css and fidelity:
                transformed = merge_css_fidelity_web(web_original, lovable_old_raw, lovable_new_raw)
                apply_mode = "css_fidelity_merge"
                delta_detail = "css_fidelity_merge"
            elif web_original:
                transformed = preserve_bridge_imports(web_original, transformed)
                transformed = preserve_lovable_asset_imports(
                    lovable_new_raw,
                    transformed,
                    tokens=tokens,
                    lovable_root=lovable_root,
                )
                transformed = preserve_web_exports(web_original, transformed)
            delta_detail = delta_detail or ("full_sync" if web_original else "")
            if web_original and transformed.strip() == web_original.strip():
                result.skipped.append({**base, "tier": "skipped", "reason": "full_sync_sin_cambios"})
                continue
            full_reg_cfg = dict(reg_cfg)
            if effective_mode == "auto" and web_original and not fidelity:
                full_reg_cfg = {
                    **full_reg_cfg,
                    "maxAbsoluteWebLineDelta": max(int(full_reg_cfg.get("maxAbsoluteWebLineDelta", 30)), 500),
                    "maxWebLineDeltaMultiplier": max(float(full_reg_cfg.get("maxWebLineDeltaMultiplier", 3)), 50),
                }
            if web_original and lovable_old_raw and not fidelity_override:
                ok, violations = check_regression(
                    web_original, transformed, lovable_old_raw, lovable_new_raw, full_reg_cfg
                )
                if not ok:
                    if fidelity:
                        fidelity_override = True
                        delta_detail = (delta_detail or "full_sync") + ";fidelity_override"
                    else:
                        result.cursor_required.append({
                            **base,
                            "tier": "cursor",
                            "reason": f"anti_regression_full ({'; '.join(violations[:3])})",
                        })
                        continue
            elif web_original and not fidelity_override:
                ok, violations = check_regression(
                    web_original, transformed, lovable_new_raw, lovable_new_raw, full_reg_cfg
                )
                if not ok:
                    if fidelity:
                        fidelity_override = True
                        delta_detail = (delta_detail or "full_sync") + ";fidelity_override"
                    else:
                        result.cursor_required.append({
                            **base,
                            "tier": "cursor",
                            "reason": f"anti_regression_full ({'; '.join(violations[:3])})",
                        })
                        continue

        if lovable_root is not None and not fidelity:
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
                "webExistedBeforeApply": web_existed_before,
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
            "webExistedBeforeApply": web_existed_before,
            "deltaDetail": delta_detail,
            "bytes": len(transformed),
            "hardcodedRemaining": len(hardcoded),
        })

    return result
