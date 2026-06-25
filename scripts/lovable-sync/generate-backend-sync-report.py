#!/usr/bin/env python3
"""BSF — Genera reporte markdown de sincronización backend."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"
sys.path.insert(0, str(AGENTS_DIR))

from agent_base import artifacts_dir, cicd_root, gh_output, write_report

try:
    from backend_sync_log import read_logs
except ImportError:
    def read_logs(*_a, **_k):  # type: ignore
        return []


def load_art(run_id: str, name: str) -> dict:
    p = artifacts_dir(run_id) / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="BSF generate backend sync report")
    parser.add_argument("--cicd-dir", default=os.environ.get("CICD_DIR", ""))
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    args = parser.parse_args()

    run_id = args.run_id
    cicd = Path(args.cicd_dir).resolve() if args.cicd_dir else cicd_root()

    delta = load_art(run_id, f"backend-delta-{run_id}.json")
    coupling = load_art(run_id, f"backend-coupling-{run_id}.json")
    implement = load_art(run_id, f"backend-implement-{run_id}.json")
    healer = load_art(run_id, f"backend-healer-{run_id}.json")
    summary = load_art(run_id, f"backend-sync-summary-{run_id}.json")
    contracts = load_art(run_id, f"backend-contract-check-{run_id}.json")
    logs = read_logs(run_id)

    applied = implement.get("applied") or []
    failed = implement.get("failed") or []
    pending_contracts = [
        f for f in (contracts.get("findings") or [])
        if not f.get("implementedInDoEventsBack")
    ]

    overall = coupling.get("overallCouplingPercent", 0)
    lines = [
        "# BSF — Reporte de Sincronización Backend",
        "",
        f"**Run:** `{run_id}` | **Fecha:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Resumen ejecutivo",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Acoplamiento global | **{overall}%** |",
        f"| Acoplamiento campos | {coupling.get('fieldCouplingPercent', 'N/A')}% |",
        f"| Acoplamiento contratos | {coupling.get('contractCouplingPercent', 'N/A')}% |",
        f"| Cobertura dominios | {coupling.get('domainCoveragePercent', 'N/A')}% |",
        f"| Cambios FE→BE requeridos | {delta.get('requiresBackendCount', 0)} |",
        f"| Dominios afectados | {', '.join(delta.get('domainsAffected') or []) or 'ninguno'} |",
        "",
        "## Ajustes aplicados en backend",
        "",
    ]

    if applied:
        for a in applied:
            fields = ", ".join(a.get("fields") or []) or "—"
            lambdas = ", ".join(a.get("lambdaDirs") or []) or "—"
            lines.append(f"- **{a.get('path')}** — dominios: `{', '.join(a.get('domains') or [])}` | campos: {fields} | lambdas: `{lambdas}` | estado: {a.get('status')}")
    else:
        lines.append("_Sin implementaciones en esta ejecución._")

    lines.extend(["", "## No se pudo ajustar", ""])
    if failed or pending_contracts:
        for f in failed:
            lines.append(f"- {f}")
        for c in pending_contracts[:15]:
            lines.append(f"- Endpoint `{c.get('endpoint')}` ({c.get('lovablePath')}) — contrato no implementado en Back")
    else:
        lines.append("_Todos los items detectados fueron delegados o no había pendientes bloqueantes._")

    lines.extend([
        "",
        "## Porcentaje de acoplamiento",
        "",
        f"El **acoplamiento global es {overall}%**, calculado como:",
        "- 40% campos FE mapeados a BE",
        "- 40% contratos API implementados",
        "- 20% dominios del registry cubiertos",
        "",
        "## Logs de errores y correcciones",
        "",
    ])

    error_logs = [l for l in logs if l.get("level") in ("error", "warn") or l.get("fixApplied")]
    if error_logs:
        for log in error_logs[-30:]:
            fix = f" | fix: {log.get('fixSummary')}" if log.get("fixApplied") else ""
            err = f" | error: {log.get('error')}" if log.get("error") else ""
            lines.append(f"- `[{log.get('ts', '')}]` **{log.get('event')}** — {log.get('message')}{err}{fix}")
    else:
        lines.append("_Sin errores registrados en esta ejecución._")

    if healer.get("errorsProcessed"):
        lines.extend([
            "",
            f"### Healer",
            f"- Errores procesados: {healer.get('errorsProcessed')}",
            f"- Agente Cursor: {healer.get('cursor', {}).get('agentId', 'N/A')}",
        ])

    lines.extend([
        "",
        "## Lambdas a desplegar (DEV)",
        "",
        ", ".join(f"`{d}`" for d in (delta.get("lambdaDirsToDeploy") or [])) or "_ninguna_",
        "",
        "## Estado pipeline",
        "",
        f"- OK: **{summary.get('ok', 'N/A')}**",
        f"- Rama backend: `{summary.get('backendBranch', 'feature/cicd/dev-automation')}`",
        "",
        "---",
        "_Generado por BSF v1.0 — Backend Sync Framework_",
    ])

    reports = cicd / "Reports"
    reports.mkdir(parents=True, exist_ok=True)
    md_path = reports / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-backend-sync-{run_id}.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    result = {"ok": True, "reportPath": str(md_path), "couplingPercent": overall}
    write_report(f"backend-sync-report-{run_id}.json", result, run_id)
    gh_output("backend_report_path", str(md_path))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
