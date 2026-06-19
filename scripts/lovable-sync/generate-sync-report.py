#!/usr/bin/env python3
"""Genera reporte consolidado DSF por cada ejecución de sync."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: str) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lovable-sha", default="")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--design-before", default="")
    parser.add_argument("--design-after", default="")
    parser.add_argument("--validation", default="")
    parser.add_argument("--smoke", default="")
    parser.add_argument("--port-map", default="")
    parser.add_argument("--artifact", default="")
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-json", default="")
    args = parser.parse_args()

    manifest = load(args.manifest)
    before = load(args.design_before)
    after = load(args.design_after) or before
    validation = load(args.validation)
    smoke = load(args.smoke)
    port_map = load(args.port_map)

    before_sim = before.get("overallSimilarityPercent", 0)
    after_sim = after.get("overallSimilarityPercent", before_sim)
    changed = manifest.get("changedFiles", [])
    ui_files = [f["path"] for f in changed if f.get("kind") == "ui"]
    rules_files = [f["path"] for f in changed if f.get("kind") == "rules"]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ok = validation.get("ok", False)
    status = "✅ ÉXITO" if ok else "❌ FALLÓ"

    md = f"""# DSF Sync Report — {args.run_id}

**Estado:** {status}  
**Fecha:** {now}  
**Lovable SHA:** `{args.lovable_sha}`  
**DEV:** https://dev.doeventsapp.com

## Resumen

| Métrica | Valor |
|---------|-------|
| Similitud pre | {before_sim}% |
| Similitud post | {after_sim}% |
| Delta | {round(after_sim - before_sim, 2)}% |
| Objetivo | {validation.get('targetSimilarity', 98)}% |
| Agente ejecutado | {validation.get('agentRan', False)} |
| Deploy DEV | {validation.get('deployRan', False)} |
| Smoke tests | {validation.get('smokeOk', 'N/A')} |
| Port-map OK | {validation.get('portMapOk', True)} |
| QA promoción | {'habilitada' if validation.get('qaPromotionEnabled') else '**INHABILITADA**'} |

## Cambios Lovable detectados

- **UI:** {len(ui_files)} archivo(s)
- **Reglas:** {len(rules_files)} archivo(s)

"""
    if ui_files:
        md += "### Archivos UI\n"
        for f in ui_files[:25]:
            md += f"- `{f}`\n"
        if len(ui_files) > 25:
            md += f"- ... y {len(ui_files) - 25} más\n"

    if rules_files:
        md += "\n### Reglas YAML\n"
        for f in rules_files:
            md += f"- `{f}`\n"

    if validation.get("errors"):
        md += "\n## Errores (gates bloqueantes)\n"
        for e in validation["errors"]:
            md += f"- {e}\n"

    if validation.get("warnings"):
        md += "\n## Advertencias\n"
        for w in validation["warnings"]:
            md += f"- {w}\n"

    if smoke:
        md += f"\n## Smoke tests DEV\n"
        md += f"- Pasaron: {smoke.get('passed', 0)}/{smoke.get('total', 0)}\n"
        for t in smoke.get("tests", []):
            icon = "✅" if t.get("ok") else "❌"
            md += f"- {icon} {t.get('name', '?')}: {t.get('detail', '')}\n"

    if port_map.get("unmappedCount", 0) > 0:
        md += f"\n## Port-map sin cobertura ({port_map['unmappedCount']})\n"
        for u in port_map.get("unmapped", [])[:15]:
            md += f"- `{u}`\n"

    if args.artifact:
        md += f"\n## Artefacto build\n- `{args.artifact}`\n"

    md += """
## Próximos pasos

"""
    if ok:
        md += "- Ciclo DEV completado. Revisar https://dev.doeventsapp.com manualmente.\n"
        md += "- QA promoción permanece **inhabilitada** hasta habilitar `dsf.qaPromotion.enabled`.\n"
    else:
        md += "- Corregir errores de gates y re-ejecutar **DSF Sync DEV**.\n"
        if validation.get("requiresGapEmpalme"):
            md += "- Si similitud < 98%, el pipeline encadena gap-empalme automáticamente.\n"

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")

    report_json = {
        "runId": args.run_id,
        "timestamp": now,
        "lovableSha": args.lovable_sha,
        "ok": ok,
        "similarityBefore": before_sim,
        "similarityAfter": after_sim,
        "validation": validation,
        "smoke": smoke,
        "portMap": port_map,
        "changedUiCount": len(ui_files),
        "changedRulesCount": len(rules_files),
        "artifactPath": args.artifact,
    }
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(report_json, indent=2), encoding="utf-8")

    print(json.dumps({"ok": ok, "reportMd": str(out_md), "reportJson": args.out_json}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
