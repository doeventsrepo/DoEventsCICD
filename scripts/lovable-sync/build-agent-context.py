#!/usr/bin/env python3
"""Construye contexto enriquecido para el agente Cursor (UI + reglasActuacion)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_DIFF_LINES = 400
MAX_RULE_CHARS = 12000


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL)


def rev_exists(cwd: Path, rev: str) -> bool:
    try:
        git(["rev-parse", "--verify", f"{rev}^{{commit}}"], cwd)
        return True
    except subprocess.CalledProcessError:
        return False


def normalize_refs(lovable: Path, before: str, after: str, lovable_sha: str | None) -> tuple[str, str]:
    if after in ("HEAD", "") and lovable_sha:
        after = lovable_sha
    if not rev_exists(lovable, after):
        after = git(["rev-parse", "HEAD"], lovable)
    before = before if rev_exists(lovable, before) else git(["rev-list", "--max-parents=0", "HEAD"], lovable)
    return before, after


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 40] + "\n\n... [truncado] ...\n"


def main() -> int:
    if len(sys.argv) < 4:
        print("Uso: build-agent-context.py <lovable_dir> <web_dir> <manifest.json> [output.md]")
        return 1

    lovable = Path(sys.argv[1])
    web = Path(sys.argv[2])
    manifest_path = Path(sys.argv[3])
    output = Path(sys.argv[4]) if len(sys.argv) > 4 else lovable / ".ai" / "agent-sync-context.md"
    cicd_dir = Path(os.environ.get("CICD_DIR", "")) if os.environ.get("CICD_DIR") else None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    before = manifest.get("before", "HEAD~1")
    after = manifest.get("after", manifest.get("lovableSha", "HEAD"))
    before, after = normalize_refs(lovable, before, after, manifest.get("lovableSha"))
    changed = manifest.get("changedFiles", [])
    design_intent = manifest.get("designIntent") or {}

    sections: list[str] = [
        "# Contexto de sincronizacion Lovable -> DoEventsWEB",
        "",
        f"- Lovable SHA: `{manifest.get('lovableSha', after)}`",
        f"- Diff: `{before}` .. `{after}`",
        f"- Cambios UI: {manifest.get('hasUiChanges', False)}",
        f"- Cambios reglas: {manifest.get('hasRulesChanges', False)}",
        "",
    ]

    if design_intent.get("userPrompt"):
        sections.extend([
            "## Intención del cambio (DCR)",
            "",
            f"**Prompt / commit:** {design_intent.get('userPrompt', '')}",
            "",
        ])
        criteria = design_intent.get("acceptanceCriteria") or []
        if criteria:
            sections.append("**Criterios de aceptación:**")
            for c in criteria:
                sections.append(f"- {c}")
            sections.append("")

    rules_files = [f for f in changed if f.get("kind") == "rules" or str(f.get("path", "")).startswith("reglasActuacion/")]
    design_rules = [f for f in changed if f.get("kind") == "design-rules" or str(f.get("path", "")).startswith("reglasDiseno/")]
    ui_files = [f for f in changed if f.get("kind") == "ui" or str(f.get("path", "")).startswith("src/")]

    if design_rules or (lovable / "reglasDiseno").exists():
        sections.append("## Reglas de diseño (reglasDiseno/)")
        sections.append("")
        sections.append("Tokens, breakpoints y convenciones de componentes para empalme y similitud ≥98%.")
        sections.append("")
        for name in ("tokens.yml", "breakpoints.yml", "component-conventions.yml"):
            p = lovable / "reglasDiseno" / name
            if p.exists():
                content = truncate(p.read_text(encoding="utf-8"), 4000)
                sections.append(f"### `{name}`")
                sections.append("```yaml")
                sections.append(content.rstrip())
                sections.append("```")
                sections.append("")

    if rules_files:
        sections.append("## Reglas de negocio modificadas (reglasActuacion/)")
        sections.append("")
        sections.append(
            "Estas reglas son la **fuente de verdad** de logica frontend: validaciones, "
            "workflows, habilitacion de botones, visibilidad de secciones y acciones UI."
        )
        sections.append("")
        for entry in rules_files:
            rel = entry["path"] if isinstance(entry, dict) else str(entry)
            rule_path = lovable / rel
            if not rule_path.exists():
                continue
            content = truncate(rule_path.read_text(encoding="utf-8"), MAX_RULE_CHARS)
            sections.append(f"### `{rel}`")
            sections.append("")
            sections.append("```yaml")
            sections.append(content.rstrip())
            sections.append("```")
            sections.append("")

    if ui_files:
        sections.append("## Archivos UI modificados (src/)")
        sections.append("")
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from empalme_rules import build_change_manifest_enriched

            ui_paths = [e["path"] if isinstance(e, dict) else str(e) for e in ui_files]
            enriched = build_change_manifest_enriched(lovable, ui_paths)
            sections.append("### Enrutamiento agentes (capas DSF)")
            sections.append("")
            sections.append("| Archivo | Capas | Agente | Complejidad |")
            sections.append("|---------|-------|--------|-------------|")
            for row in enriched:
                layers = ", ".join(row.get("layers") or [])
                sections.append(
                    f"| `{row.get('lovablePath', '')}` | {layers or '—'} | "
                    f"{row.get('agentTier', 'python')} | {row.get('complexity', 'simple')} |"
                )
            sections.append("")
        except Exception:
            pass
        for entry in ui_files:
            rel = entry["path"] if isinstance(entry, dict) else str(entry)
            sections.append(f"- `{rel}` (`{entry.get('status', 'M') if isinstance(entry, dict) else 'M'}`)")
        sections.append("")
        try:
            diff = git(
                ["diff", f"{before}..{after}", "--", "src/", "public/"],
                lovable,
            )
            diff_text = diff.decode() if isinstance(diff, bytes) else diff
            lines = diff_text.splitlines()
            if len(lines) > MAX_DIFF_LINES:
                diff_text = "\n".join(lines[:MAX_DIFF_LINES]) + f"\n\n... [{len(lines) - MAX_DIFF_LINES} lineas omitidas] ..."
            sections.append("### Diff resumido")
            sections.append("")
            sections.append("```diff")
            sections.append(diff_text.rstrip() or "(sin diff en src/)")
            sections.append("```")
            sections.append("")
        except subprocess.CalledProcessError:
            sections.append("_No se pudo generar diff git._")
            sections.append("")

    port_map = web / ".lovable-port-map.json"
    if port_map.exists():
        sections.append("## Mapeo de rutas (.lovable-port-map.json)")
        sections.append("")
        sections.append("```json")
        sections.append(port_map.read_text(encoding="utf-8").strip())
        sections.append("```")
        sections.append("")

    sections.extend(
        [
            "## Arquitectura DoEventsWEB (recordatorio)",
            "",
            "| Capa | Ruta | Rol |",
            "|---|---|---|",
            "| UI Lovable portada | `packages/shell/src/lovable/` | Componentes, contexts, data mocks |",
            "| Bridge / wiring | `packages/shell/src/lovable-bridge/` | Adaptadores API, providers, layout |",
            "| Paginas reales | `packages/shell/src/pages/` | Rutas React Router del shell |",
            "| Shared API | `packages/shared/src/` | Clientes HTTP, tipos, auth |",
            "| Reglas agente (DoEventsWEB) | `ReglasAgente/` | Artefactos obligatorios del agente Cursor |",
            "| Reglas negocio YAML (Lovable) | `reglasActuacion/` en discover-joyful-feed | Fuente de reglas funcionales |",
            "| Orquestacion CI/CD | repo `DoEventsCICD` | Scripts, `Reglas/`, workflows |",
            "",
            "- Imports Lovable `@/` -> alias Vite `@` y `@lovable` apuntan a `src/lovable/`.",
            "- **Responsive**: diseno mobile-first (`max-w-lg` en layout); validar en viewport movil y desktop.",
            "- Backend: solo modificar DoEventsBack si la regla lo exige y el modo lo autoriza.",
            "",
        ]
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Contexto agente: {output} ({len(sections)} secciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
