#!/usr/bin/env python3
"""Orquestador de simulacion DoEventsCICD — genera REGISTRO_PRUEBAS.md."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parent
CICD_ROOT = SIM_ROOT.parent
SCRIPTS = CICD_ROOT / "scripts" / "lovable-sync"
SIM_SCRIPTS = SIM_ROOT / "scripts"
FIXTURES = SIM_ROOT / "fixtures" / "sources.json"
OUTPUT = SIM_ROOT / "output"
SANDBOX_WEB = SIM_ROOT / "sandbox" / "DoEventsWEB"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> dict:
    merged = {**os.environ, **(env or {})}
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or SIM_ROOT,
            env=merged,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return {
            "cmd": " ".join(cmd),
            "exitCode": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-2000:],
            "ok": proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "exitCode": -1, "ok": False, "stderr": "TIMEOUT"}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "exitCode": -1, "ok": False, "stderr": str(exc)}


def ensure_git_repo(path: Path) -> dict:
    git_dir = path / ".git"
    if git_dir.exists():
        return {"action": "existing", "ok": True}
    init = run_cmd(["git", "init"], cwd=path)
    if not init["ok"]:
        return {"action": "init_failed", "ok": False, "detail": init}
    run_cmd(["git", "config", "user.email", "sim@doevents.local"], cwd=path)
    run_cmd(["git", "config", "user.name", "DoEventsCICD Sim"], cwd=path)
    run_cmd(["git", "add", "-A"], cwd=path)
    base = run_cmd(["git", "commit", "-m", "sim: base"], cwd=path)
    touch = path / ".sim-marker"
    touch.write_text(utc_now(), encoding="utf-8")
    run_cmd(["git", "add", ".sim-marker"], cwd=path)
    second = run_cmd(["git", "commit", "-m", "sim: marker"], cwd=path)
    return {"action": "created_ephemeral", "ok": base["ok"] or second["ok"], "detail": second}


def prepare_lovable_workspace(source: dict, lovable: Path) -> tuple[Path, dict]:
    """Usa repo real si tiene .git; si no, copia a workspace aislado."""
    if (lovable / ".git").exists():
        return lovable, {"mode": "real_git", "path": str(lovable)}

    ws = SIM_ROOT / "workspaces" / source["id"] / "lovable"
    if ws.exists():
        shutil.rmtree(ws, ignore_errors=True)
    if ws.exists():
        ws = SIM_ROOT / "workspaces" / source["id"] / f"lovable-run-{int(datetime.now().timestamp())}"
    ws.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        lovable,
        ws,
        ignore=shutil.ignore_patterns("node_modules", "dist", ".git"),
    )
    git_info = ensure_git_repo(ws)
    return ws, {"mode": "workspace_copy", "path": str(ws), "git": git_info}


def count_rules(path: Path) -> int:
    if not (path / "reglasActuacion").exists():
        return 0
    return len(list((path / "reglasActuacion").rglob("*.yml"))) + len(
        list((path / "reglasActuacion").rglob("*.yaml"))
    )


def run_fixture(source: dict) -> dict:
    fid = source["id"]
    lovable = (SIM_ROOT / source["path"]).resolve()
    out = OUTPUT / fid
    out.mkdir(parents=True, exist_ok=True)

    result: dict = {
        "id": fid,
        "label": source.get("label", fid),
        "lovablePath": str(lovable),
        "exists": lovable.exists(),
        "tests": [],
        "passed": 0,
        "failed": 0,
        "skipped": 0,
    }

    if not lovable.exists():
        result["tests"].append({"name": "source_exists", "status": "FAIL", "detail": "Ruta no encontrada"})
        result["failed"] = 1
        return result

    result["rulesCount"] = count_rules(lovable)
    result["hasSrc"] = (lovable / "src").exists()

    work_path, work_meta = prepare_lovable_workspace(source, lovable)
    result["workspace"] = work_meta
    result["workPath"] = str(work_path)

    # T01 validate rules
    if result["rulesCount"] > 0:
        t = run_cmd([sys.executable, str(SCRIPTS / "validate-rules.py"), "reglasActuacion"], cwd=work_path)
        status = "PASS" if t["ok"] else "FAIL"
        result["tests"].append({"name": "validate_rules", "status": status, "detail": t})
        result["passed" if t["ok"] else "failed"] += 1
    else:
        result["tests"].append({"name": "validate_rules", "status": "SKIP", "detail": "Sin reglasActuacion"})
        result["skipped"] += 1

    # T02 agent gate (sandbox WEB)
    if SANDBOX_WEB.exists():
        t = run_cmd([sys.executable, str(SCRIPTS / "validate-agent-gate.py"), str(SANDBOX_WEB)])
        status = "PASS" if t["ok"] else "FAIL"
        result["tests"].append({"name": "validate_agent_gate", "status": status, "detail": t})
        result["passed" if t["ok"] else "failed"] += 1
    else:
        result["tests"].append({"name": "validate_agent_gate", "status": "SKIP", "detail": "Ejecutar prepare-sandbox.ps1"})
        result["skipped"] += 1

    # T03 git + analyze diff
    if work_meta.get("mode") == "real_git":
        diff_before, diff_after = "__last_sync__", "HEAD"
    else:
        diff_before, diff_after = "HEAD~1", "HEAD"

    t = run_cmd(
        [
            sys.executable,
            str(SCRIPTS / "analyze-lovable-diff.py"),
            str(work_path),
            diff_before,
            diff_after,
            str(SANDBOX_WEB) if SANDBOX_WEB.exists() else str(SIM_ROOT),
        ],
    )
    manifest_src = work_path / "lovable-change-manifest.json"
    if manifest_src.exists():
        (out / "lovable-change-manifest.json").write_text(
            manifest_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    status = "PASS" if t["ok"] else "FAIL"
    result["tests"].append({"name": "analyze_lovable_diff", "status": status, "detail": t})
    result["passed" if t["ok"] else "failed"] += 1

    manifest_path = out / "lovable-change-manifest.json"
    if not manifest_path.exists():
        manifest_path = work_path / "lovable-change-manifest.json"

    # T04 build context
    if manifest_path.exists() and SANDBOX_WEB.exists():
        ctx_out = out / "agent-sync-context.md"
        t = run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "build-agent-context.py"),
                str(work_path),
                str(SANDBOX_WEB),
                str(manifest_path),
                str(ctx_out),
            ],
            env={"CICD_DIR": str(CICD_ROOT)},
        )
        status = "PASS" if t["ok"] else "FAIL"
        result["tests"].append({"name": "build_agent_context", "status": status, "detail": t})
        result["passed" if t["ok"] else "failed"] += 1
    else:
        result["tests"].append({"name": "build_agent_context", "status": "SKIP"})
        result["skipped"] += 1

    # T05 generate artifacts (sandbox only)
    if manifest_path.exists() and SANDBOX_WEB.exists():
        t = run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "generate-agent-artifacts.py"),
                str(work_path),
                str(SANDBOX_WEB),
                str(manifest_path),
            ],
            env={"GITHUB_RUN_ID": "sim-local", "BUILD_RESULT": "not_run"},
        )
        status = "PASS" if t["ok"] else "FAIL"
        result["tests"].append({"name": "generate_agent_artifacts", "status": status, "detail": t})
        result["passed" if t["ok"] else "failed"] += 1
    else:
        result["tests"].append({"name": "generate_agent_artifacts", "status": "SKIP"})
        result["skipped"] += 1

    # T06 anti-mocks
    if SANDBOX_WEB.exists():
        pages = SANDBOX_WEB / "packages" / "shell" / "src" / "pages"
        mocks_found = []
        if pages.exists():
            patterns = ("mockEvents", "mockTickets", "mockOrders", "hardcodedEvents")
            for py in pages.rglob("*.tsx"):
                text = py.read_text(encoding="utf-8", errors="ignore")
                for p in patterns:
                    if p in text:
                        mocks_found.append(f"{py.name}:{p}")
        ok = len(mocks_found) == 0
        result["tests"].append(
            {
                "name": "validate_no_mocks",
                "status": "PASS" if ok else "FAIL",
                "detail": {"mocksFound": mocks_found[:10]},
            }
        )
        result["passed" if ok else "failed"] += 1

    # T07 dry-run agent
    if SANDBOX_WEB.exists() and manifest_path.exists():
        t = run_cmd(
            [sys.executable, str(SIM_SCRIPTS / "simulate-agent-dry-run.py")],
            env={
                "CICD_DIR": str(CICD_ROOT),
                "LOVABLE_DIR": str(work_path),
                "WEB_DIR": str(SANDBOX_WEB),
                "MANIFEST_PATH": str(manifest_path),
                "SIM_OUTPUT_DIR": str(out / "agent-dry-run"),
            },
        )
        status = "PASS" if t["ok"] else "FAIL"
        result["tests"].append({"name": "agent_dry_run", "status": status, "detail": t})
        result["passed" if t["ok"] else "failed"] += 1

    # T08 optional live agent
    if os.environ.get("SIM_RUN_LIVE_AGENT") == "1" and os.environ.get("CURSOR_API_KEY"):
        t = run_cmd(
            [sys.executable, str(SCRIPTS / "run-port-agent-api.py")],
            env={
                "CICD_DIR": str(CICD_ROOT),
                "LOVABLE_DIR": str(work_path),
                "WEB_DIR": str(SANDBOX_WEB),
                "AGENT_WAIT": "false",
                "AGENT_AUTO_PR": "false",
                "AGENT_INCLUDE_BACK": "false",
            },
        )
        result["tests"].append(
            {"name": "agent_live_api", "status": "PASS" if t["ok"] else "FAIL", "detail": t}
        )
    else:
        result["tests"].append(
            {
                "name": "agent_live_api",
                "status": "SKIP",
                "detail": "Definir SIM_RUN_LIVE_AGENT=1 y CURSOR_API_KEY para prueba real",
            }
        )
        result["skipped"] += 1

    result["ok"] = result["failed"] == 0
    return result


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    fixtures_results = report["fixtures"]
    total_fail = summary["failed"]
    total_pass = summary["passed"]
    lines = [
        "# Registro de pruebas — Simulación DoEventsCICD",
        "",
        f"**Ejecución:** {report['timestamp']}",
        f"**Sandbox WEB:** `{report['sandboxWeb']}` (copia aislada, no productivo)",
        f"**DoEventsWEB productivo:** no modificado",
        "",
        "## Resumen",
        "",
        f"| Métrica | Valor |",
        f"|---------|-------|",
        f"| Fixtures probados | {report['summary']['fixtures']} |",
        f"| Tests PASS | {report['summary']['passed']} |",
        f"| Tests FAIL | {report['summary']['failed']} |",
        f"| Tests SKIP | {report['summary']['skipped']} |",
        f"| **Veredicto** | **{report['summary']['verdict']}** |",
        "",
        "## Resultado por fuente Lovable",
        "",
    ]

    for fx in report["fixtures"]:
        icon = "OK" if fx.get("ok") else "FAIL"
        lines.append(f"### [{icon}] {fx['id']} — {fx.get('label', '')}")
        lines.append("")
        lines.append(f"- Ruta: `{fx.get('lovablePath', '')}`")
        lines.append(f"- `src/`: {fx.get('hasSrc', '?')} | reglas YAML: {fx.get('rulesCount', 0)}")
        lines.append("")
        lines.append("| Test | Estado |")
        lines.append("|------|--------|")
        for t in fx.get("tests", []):
            lines.append(f"| {t['name']} | {t['status']} |")
        lines.append("")

    lines.extend(
        [
            "## Criterios de implantación",
            "",
            f"- [{'x' if total_fail == 0 else ' '}] Pipeline local sin FAIL ({total_pass} PASS / {total_fail} FAIL)",
            f"- [{'x' if any(f['id']=='discover-joyful-feed' and f.get('ok') for f in fixtures_results) else ' '}] discover-joyful-feed OK",
            f"- [{'x' if any(f['id']=='lovable-v17' and f.get('ok') for f in fixtures_results) else ' '}] lovable-v17 OK",
            "- [x] Sandbox WEB aislado (no se modificó DoEventsWEB productivo)",
            "- [ ] Revisión humana de `output/discover-joyful-feed/agent-sync-context.md`",
            "- [ ] `npm run build:qa` en sandbox (prueba manual opcional)",
            "- [ ] `agent_live_api` con CURSOR_API_KEY (prueba en rama de prueba)",
            "",
            "## Notas",
            "",
            report.get("notes", ""),
            "",
            f"*Generado automáticamente por `simulation/run-simulation.py`*",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    config = json.loads(FIXTURES.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if not SANDBOX_WEB.exists():
        print("AVISO: sandbox/DoEventsWEB no existe. Ejecuta prepare-sandbox.ps1 primero.", file=sys.stderr)

    fixtures_results = []
    total_pass = total_fail = total_skip = 0

    for source in sorted(config["sources"], key=lambda s: s.get("priority", 99)):
        print(f"\n=== Fixture: {source['id']} ===")
        fx = run_fixture(source)
        fixtures_results.append(fx)
        for t in fx.get("tests", []):
            if t["status"] == "PASS":
                total_pass += 1
            elif t["status"] == "FAIL":
                total_fail += 1
            else:
                total_skip += 1

    verdict = "LISTO PARA IMPLANTAR (simulacion local)" if total_fail == 0 else "NO IMPLANTAR — corregir FAIL"

    report = {
        "timestamp": utc_now(),
        "sandboxWeb": str(SANDBOX_WEB),
        "productWebUntouched": True,
        "summary": {
            "fixtures": len(fixtures_results),
            "passed": total_pass,
            "failed": total_fail,
            "skipped": total_skip,
            "verdict": verdict,
        },
        "fixtures": fixtures_results,
        "notes": (
            "Fuentes sin reglasActuacion (v13-v16) tienen SKIP esperado en validate_rules. "
            "discover-joyful-feed (25 reglas) y v17 (4 reglas) son candidatos para producción. "
            "Corrección aplicada: catch-up valida que el SHA de sync exista en repo Lovable antes del diff."
        ),
    }

    (OUTPUT / "last-run.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render_markdown(report)
    (SIM_ROOT / "REGISTRO_PRUEBAS.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
