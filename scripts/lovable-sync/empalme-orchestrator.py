#!/usr/bin/env python3
"""
Orquestador DSF empalme — Python primero, Cursor solo como refuerzo puntual (sin loops).

Flujo:
  1. Comparación diseño (before)
  2. Agente Python (solo archivos del diff Lovable)
  3. Comparación (after)
  4. [Opcional] Un único escalado Cursor (max N archivos, sin loop)
  5. Reporte empalme (aplicado / manual / cursor / backend)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CICD_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = CICD_ROOT / "scripts" / "lovable-sync"


def run(cmd: list[str], *, env: dict | None = None) -> int:
    print(f"$ {' '.join(cmd)}", flush=True)
    merged = {**os.environ, **(env or {})}
    return subprocess.call(cmd, env=merged)


def load_strategy(cicd_dir: Path) -> dict:
    cfg_path = cicd_dir / "cicd.config.json"
    if not cfg_path.is_file():
        return {}
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    return cfg.get("dsf", {}).get("empalmeStrategy", {})


def gh_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def similarity(path: Path) -> float:
    return float(json.loads(path.read_text(encoding="utf-8"))["overallSimilarityPercent"])


def build_cursor_manifest(cicd: Path, run_id: str, cursor_items: list[dict], batch_size: int) -> Path:
    """Manifiesto mínimo para un único batch Cursor (sin loop)."""
    gaps = []
    for item in cursor_items[:batch_size]:
        gaps.append({
            "lovablePath": item.get("lovablePath", ""),
            "webPath": item.get("webPath", ""),
            "status": item.get("status", "needs_adaptation"),
            "similarityPercent": item.get("similarityPercent", 0),
            "area": "Escalado Cursor",
            "feature": Path(item.get("lovablePath", "")).stem,
            "where": "Empalme reforzado",
            "action": "Empalmar con Cursor API (escalado único)",
            "checks": ["Comparar visualmente con Lovable"],
            "component": Path(item.get("lovablePath", "")).stem,
        })
    manifest = {
        "version": "1.0",
        "purpose": "Escalado único Cursor — sin loop",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "workflowRunId": f"{run_id}-cursor-escalation",
        "totalPendingGaps": len(cursor_items),
        "batchSize": len(gaps),
        "batchIndex": 1,
        "gapsInBatch": len(gaps),
        "remainingAfterBatch": max(0, len(cursor_items) - len(gaps)),
        "gaps": gaps,
    }
    out = cicd / f"gap-manifest-cursor-escalation-{run_id}.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="DSF Empalme Orchestrator (Python-first)")
    parser.add_argument("--lovable-dir", required=True)
    parser.add_argument("--web-dir", required=True)
    parser.add_argument("--cicd-dir", default=str(CICD_ROOT))
    parser.add_argument("--port-map", required=True)
    parser.add_argument("--change-manifest", default="")
    parser.add_argument("--diff-intelligence", default="")
    parser.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "local"))
    parser.add_argument("--cursor-fallback", action="store_true", help="Permitir un escalado Cursor si quedan items")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cicd = Path(args.cicd_dir).resolve()
    strategy = load_strategy(cicd)
    scope = strategy.get("scope", "diff-only")
    python_max_sim = float(strategy.get("pythonMaxSimApply", 85))
    max_items = int(strategy.get("maxPythonFilesPerRun", 50))
    max_cursor = int(strategy.get("maxCursorFilesPerRun", 5))
    max_cursor_escalations = int(strategy.get("maxCursorEscalations", 1))
    cursor_enabled_cfg = bool(strategy.get("cursorFallbackEnabled", True))
    lovable_path = Path(args.lovable_dir).resolve()
    try:
        from quality_policy import cursor_policy, load_quality_policy

        cp = cursor_policy(load_quality_policy(lovable_path))
        max_cursor = int(cp.get("maxFilesPerRun", max_cursor))
        max_cursor_escalations = min(max_cursor_escalations, int(cp.get("maxEscalations", max_cursor_escalations)))
        cursor_auto = cp.get("autoEscalateWhenPythonFails", strategy.get("cursorAutoEscalate", True))
        cursor_default_on = bool(cp.get("enabledByDefault", False))
    except ImportError:
        cursor_auto = strategy.get("cursorAutoEscalate", True)
        cursor_default_on = False
        cp = {}

    before_path = cicd / f"design-comparison-before-{args.run_id}.json"
    after_python = cicd / f"design-comparison-after-python-{args.run_id}.json"
    after_final = cicd / f"design-comparison-after-{args.run_id}.json"
    python_result = cicd / f"empalme-python-result-{args.run_id}.json"

    compare = SCRIPTS / "compare-design-similarity.py"
    python_agent = SCRIPTS / "run-python-empalme.py"
    report_script = SCRIPTS / "generate-empalme-report.py"
    cursor_agent = SCRIPTS / "run-gap-empalme-agent.py"

    rc = run([
        sys.executable, str(compare),
        args.lovable_dir, args.web_dir, args.port_map, str(before_path),
    ])
    if rc != 0:
        return rc

    sim_before = similarity(before_path)
    print(f"Similitud before: {sim_before}%")

    py_cmd = [
        sys.executable, str(python_agent),
        "--lovable-dir", args.lovable_dir,
        "--web-dir", args.web_dir,
        "--port-map", args.port_map,
        "--comparison", str(before_path),
        "--scope", scope,
        "--python-max-sim", str(python_max_sim),
        "--max-items", str(max_items),
        "--out", str(python_result),
        "--run-id", args.run_id,
    ]
    if args.change_manifest:
        py_cmd.extend(["--change-manifest", args.change_manifest])
    if args.dry_run:
        py_cmd.append("--dry-run")
    rc = run(py_cmd)
    if rc != 0:
        return rc

    anti_reg_script = CICD_ROOT / "scripts" / "agents" / "run-anti-regression-guard-agent.py"
    if anti_reg_script.is_file() and not args.dry_run:
        print("Ejecutando anti-regression-guard post-empalme Python...")
        rc_ar = run([
            sys.executable, str(anti_reg_script),
            "--lovable-dir", args.lovable_dir,
            "--web-dir", args.web_dir,
            "--cicd-dir", str(cicd),
            "--run-id", args.run_id,
            "--python-result", str(python_result),
        ])
        if rc_ar != 0:
            print("BLOQUEADO: anti-regression-guard — empalme con regresión detectada", file=sys.stderr)
            return rc_ar

    py_data = json.loads(python_result.read_text(encoding="utf-8"))
    cursor_used = False

    if not args.dry_run and py_data.get("appliedCount", 0) > 0:
        run([
            sys.executable, str(compare),
            args.lovable_dir, args.web_dir, args.port_map, str(after_python),
        ])
        sim_after_python = similarity(after_python)
    else:
        after_python = before_path
        sim_after_python = sim_before

    sim_final = sim_after_python
    after_path = after_python

    cursor_items = py_data.get("cursorRequired") or []
    has_api_key = bool(os.environ.get("CURSOR_API_KEY"))

    # Agentes 5-6: guards antes de Cursor (sin loops)
    guards_blocked = False
    manifest_path = Path(args.change_manifest) if args.change_manifest else None
    if manifest_path and manifest_path.is_file() and not args.dry_run:
        for guard_name in ("run-dependency-guard-agent.py", "run-backend-contract-check-agent.py"):
            guard_script = CICD_ROOT / "scripts" / "agents" / guard_name
            if guard_script.is_file():
                print(f"Ejecutando {guard_name} antes de cursor-escalation...")
                rc_guard = run([
                    sys.executable, str(guard_script),
                    "--lovable-dir", args.lovable_dir,
                    "--change-manifest", str(manifest_path),
                    "--run-id", args.run_id,
                ])
                if rc_guard != 0:
                    guards_blocked = True
                    print(f"BLOQUEADO: {guard_name} — cursor cancelado", file=sys.stderr)

        release_script = CICD_ROOT / "scripts" / "agents" / "run-release-guard-agent.py"
        if release_script.is_file():
            print("Ejecutando release-guard antes de cursor-escalation...")
            rc_rg = run([
                sys.executable, str(release_script),
                "--lovable-dir", args.lovable_dir,
                "--change-manifest", str(manifest_path),
                "--run-id", args.run_id,
            ])
            if rc_rg != 0:
                guards_blocked = True
                print("BLOQUEADO: release-guard — cursor cancelado", file=sys.stderr)

    # Validar precondiciones Cursor según prompt maestro
    diff_intel = {}
    if args.diff_intelligence and Path(args.diff_intelligence).is_file():
        diff_intel = json.loads(Path(args.diff_intelligence).read_text(encoding="utf-8"))

    cursor_preconditions = (
        not guards_blocked
        and (diff_intel.get("decision", {}).get("status") != "blocked" if diff_intel else True)
        and (diff_intel.get("risk", {}).get("level") != "blocked" if diff_intel else True)
    )

    should_cursor = (
        cursor_items
        and has_api_key
        and not args.dry_run
        and cursor_preconditions
        and cursor_enabled_cfg
        and max_cursor_escalations > 0
        and (args.cursor_fallback or cursor_auto or cursor_default_on)
    )
    if cursor_items and not has_api_key and not args.dry_run:
        print("AVISO: Python dejó items para Cursor pero falta CURSOR_API_KEY — ver reporte manualRequired/cursorRequired", file=sys.stderr)
    elif cursor_items and not should_cursor and not args.dry_run:
        print(
            "AVISO: Cursor deshabilitado por config/flags — items pendientes en cursorRequired",
            file=sys.stderr,
        )

    if should_cursor:
        manifest = build_cursor_manifest(cicd, args.run_id, cursor_items, max_cursor)
        os.environ["GAP_MANIFEST_PATH"] = str(manifest)
        os.environ.setdefault("LOVABLE_DIR", args.lovable_dir)
        os.environ.setdefault("WEB_DIR", args.web_dir)
        os.environ.setdefault("CICD_DIR", str(cicd))
        print(f"Cursor refuerzo único — {min(len(cursor_items), max_cursor)} archivos (maxRetries=0, sin loop)")
        rc_cursor = run([sys.executable, str(cursor_agent)])
        cursor_used = rc_cursor == 0
        if cursor_used:
            run([
                sys.executable, str(compare),
                args.lovable_dir, args.web_dir, args.port_map, str(after_final),
            ])
            after_path = after_final
            sim_final = similarity(after_final)
        else:
            print("AVISO: Cursor escalation falló — items quedan en reporte para revisión manual", file=sys.stderr)

    change_manifest_script = SCRIPTS / "build-dsf-change-manifest.py"
    if change_manifest_script.is_file():
        run([
            sys.executable, str(change_manifest_script),
            "--lovable-dir", args.lovable_dir,
            "--python-result", str(python_result),
            "--summary", f"DSF empalme run {args.run_id}",
            "--run-id", args.run_id,
            "--out", str(cicd / f"dsf-change-manifest-{args.run_id}.json"),
            *(["--cursor-used"] if cursor_used else []),
        ])

    summary = {
        "runId": args.run_id,
        "strategy": "python-first",
        "loopDisabled": True,
        "similarityBefore": sim_before,
        "similarityAfterPython": sim_after_python,
        "similarityFinal": sim_final,
        "similarityDelta": round(sim_final - sim_before, 2),
        "pythonApplied": py_data.get("appliedCount", 0),
        "cursorEscalationUsed": cursor_used,
        "cursorRequiredRemaining": len(cursor_items) if not cursor_used else max(0, len(cursor_items) - max_cursor),
        "manualRequired": py_data.get("manualRequiredCount", 0),
        "backendRequired": py_data.get("backendRequiredCount", 0),
        "dryRun": args.dry_run,
    }
    summary_path = cicd / f"empalme-summary-{args.run_id}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if report_script.is_file():
        run([
            sys.executable, str(report_script),
            "--before", str(before_path),
            "--after", str(after_path),
            "--python-result", str(python_result),
            "--summary", str(summary_path),
            "--out-md", str(cicd / "Reports" / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-empalme-{args.run_id}.md"),
            "--out-json", str(cicd / f"empalme-report-{args.run_id}.json"),
        ])

    gh_output("similarity_before", str(sim_before))
    gh_output("similarity_after", str(sim_final))
    gh_output("python_applied", str(py_data.get("appliedCount", 0)))
    gh_output("cursor_escalation", str(cursor_used).lower())

    print(json.dumps(summary, indent=2))

    manifest = {}
    if args.change_manifest and Path(args.change_manifest).is_file():
        manifest = json.loads(Path(args.change_manifest).read_text(encoding="utf-8"))
    ui_changed = bool(manifest.get("hasUiChanges")) or any(
        f.get("kind") == "ui" for f in manifest.get("changedFiles", [])
    )
    applied = int(py_data.get("appliedCount", 0))
    if (
        not args.dry_run
        and ui_changed
        and applied == 0
        and not cursor_used
        and int(py_data.get("cursorRequiredCount", 0)) > 0
    ):
        print(
            "ERROR: hay cambios UI en Lovable pero el empalme no aplicó ninguno "
            f"(cursorRequired={py_data.get('cursorRequiredCount')})",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
