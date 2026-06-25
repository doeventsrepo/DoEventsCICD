#!/usr/bin/env python3
"""
Validación local del pipeline multiagente DSF + BSF.

Simula cambios frontend que requieren backend, ejecuta orquestadores en dry-run
y verifica que todos los agentes del registry respondan correctamente.

Uso (desde DoEventsCICD/simulation):
  python run-multiagent-validation.py
  python run-multiagent-validation.py --with-cursor   # requiere CURSOR_API_KEY en local.env
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SIM_ROOT = Path(__file__).resolve().parent
CICD_ROOT = SIM_ROOT.parent
AGENTS_JSON = CICD_ROOT / "dsf" / "agents.json"
BACKEND_REGISTRY = CICD_ROOT / "dsf" / "backend-registry.json"


def load_env() -> None:
    env_path = SIM_ROOT / "local.env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


def run_cmd(cmd: list[str], env: dict | None = None, timeout: int = 600) -> dict[str, Any]:
    merged = {**os.environ, **(env or {})}
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=merged)
        return {
            "ok": proc.returncode == 0,
            "exitCode": proc.returncode,
            "stdout": (proc.stdout or "")[-3000:],
            "stderr": (proc.stderr or "")[-1500:],
            "cmd": " ".join(cmd[:6]),
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "exitCode": -1, "stderr": "TIMEOUT", "cmd": " ".join(cmd[:6])}
    except Exception as e:
        return {"ok": False, "exitCode": -1, "stderr": str(e), "cmd": " ".join(cmd[:6])}


def make_simulated_manifest(out_dir: Path) -> Path:
    """Manifiesto con cambios que deben disparar dominio events + profile."""
    manifest = {
        "lovableSha": "sim-multiagent-001",
        "mode": "simulation",
        "changedFiles": [
            {
                "status": "M",
                "path": "src/components/events/CreateEventView.tsx",
                "kind": "ui",
            },
            {
                "status": "M",
                "path": "src/components/events/StepEventDetails.tsx",
                "kind": "ui",
            },
            {
                "status": "M",
                "path": "src/components/feed/ProfileView.tsx",
                "kind": "ui",
            },
            {
                "status": "M",
                "path": "reglasActuacion/publicaciones/feed-principal.yml",
                "kind": "rules",
            },
        ],
        "hasUiChanges": True,
        "requiresAgent": True,
        "simulation": True,
    }
    path = out_dir / "lovable-change-manifest-sim.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def patch_simulated_web_snippet(web_dir: Path, tmp_dir: Path) -> Path:
    """Crea snippet TSX simulado con campos nuevos y llamada API."""
    snippet = tmp_dir / "EventWizard-sim-snippet.tsx"
    snippet.write_text(
        """
import { useState } from 'react';
import { fetch } from '@doevents/shared';

export function EventWizardSim() {
  const [eventCapacity, setEventCapacity] = useState<number>(0);
  const [sponsorTier, setSponsorTier] = useState<string>('');
  const handleSubmit = () => {
    fetch('/api/v1/events/create', {
      method: 'POST',
      body: JSON.stringify({ eventCapacity, sponsorTier, venueId: 'x' }),
    });
  };
  return (
    <form onSubmit={handleSubmit}>
      <input name="eventCapacity" id="eventCapacity" required maxLength={10} />
      <input name="sponsorTier" id="sponsorTier" />
    </form>
  );
}
""",
        encoding="utf-8",
    )
    return snippet


def test_agent_scripts_exist() -> dict[str, Any]:
    cfg = json.loads(AGENTS_JSON.read_text(encoding="utf-8"))
    missing: list[str] = []
    found: list[str] = []
    for entry in cfg.get("chain", []):
        script = entry.get("script")
        if not script:
            continue
        path = CICD_ROOT / script
        if path.is_file():
            found.append(entry["id"])
        else:
            missing.append(f"{entry['id']}: {script}")

    bsf_scripts = [
        "scripts/lovable-sync/detect-frontend-backend-delta.py",
        "scripts/agents/run-backend-sync-orchestrator.py",
        "scripts/agents/run-backend-implement-agent.py",
        "scripts/agents/run-backend-error-healer-agent.py",
        "scripts/lovable-sync/analyze-backend-coupling.py",
        "scripts/lovable-sync/generate-backend-sync-report.py",
        "scripts/load-dsf-secrets.ps1",
        "scripts/deploy/deploy-back-dev.ps1",
    ]
    for rel in bsf_scripts:
        if (CICD_ROOT / rel).is_file():
            found.append(rel)
        else:
            missing.append(rel)

    return {
        "name": "agent_scripts_exist",
        "ok": not missing,
        "found": len(found),
        "missing": missing,
    }


def test_backend_registry() -> dict[str, Any]:
    reg = json.loads(BACKEND_REGISTRY.read_text(encoding="utf-8"))
    domains = reg.get("domains") or {}
    back_root = CICD_ROOT.parent / "DoEventsBack"
    missing_dirs: list[str] = []
    for _id, meta in domains.items():
        d = meta.get("lambdaDir", "")
        if d and not (back_root / d).is_dir():
            missing_dirs.append(d)
    return {
        "name": "backend_registry",
        "ok": len(domains) >= 10,
        "domainsCount": len(domains),
        "missingLambdaDirs": missing_dirs[:5],
    }


def test_delta_detector(
    lovable: Path, web: Path, manifest: Path, run_id: str
) -> dict[str, Any]:
    r = run_cmd(
        [
            sys.executable,
            str(CICD_ROOT / "scripts" / "lovable-sync" / "detect-frontend-backend-delta.py"),
            "--lovable-dir",
            str(lovable),
            "--web-dir",
            str(web),
            "--change-manifest",
            str(manifest),
            "--run-id",
            run_id,
        ],
        env={"DSF_AGENT_DRY_RUN": "1", "CICD_DIR": str(CICD_ROOT)},
    )
    delta_path = CICD_ROOT / "artifacts" / run_id / f"backend-delta-{run_id}.json"
    delta = json.loads(delta_path.read_text(encoding="utf-8")) if delta_path.is_file() else {}
    return {
        "name": "bsf_delta_detector",
        "ok": r["ok"] and delta.get("requiresBackendCount", 0) >= 0,
        "requiresBackend": delta.get("requiresBackendCount"),
        "domains": delta.get("domainsAffected"),
        "detail": r,
    }


def test_orchestrator_phases(
    lovable: Path, web: Path, run_id: str, phase: str, fullstack: bool
) -> dict[str, Any]:
    env = {
        "DSF_AGENT_DRY_RUN": "1",
        "DSF_LOCAL_MODE": "1",
        "CICD_DIR": str(CICD_ROOT),
        "LOVABLE_DIR": str(lovable),
        "WEB_DIR": str(web),
        "GITHUB_RUN_ID": run_id,
        "DSF_LOCAL_RUN_ID": run_id,
        "DSF_CHANGE_MANIFEST": os.environ.get("DSF_CHANGE_MANIFEST", ""),
    }
    if fullstack:
        env["DSF_AGENT_MODE"] = "fullstack"
    r = run_cmd(
        [
            sys.executable,
            str(CICD_ROOT / "scripts" / "agents" / "orchestrator.py"),
            "--dry-run",
            "--phase",
            phase,
            "--lovable-dir",
            str(lovable),
            "--web-dir",
            str(web),
            "--run-id",
            run_id,
        ],
        env=env,
        timeout=900,
    )
    summary_path = CICD_ROOT / "artifacts" / run_id / "orchestrator-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    return {
        "name": f"orchestrator_{phase}",
        "ok": r["ok"] and summary.get("ok", False),
        "agentsRun": len(summary.get("results") or []),
        "failedAgents": [x.get("agent") for x in (summary.get("results") or []) if not x.get("ok")],
        "detail": r if not r["ok"] else {"exitCode": 0},
    }


def test_bsf_orchestrator(
    lovable: Path, web: Path, back: Path, manifest: Path, run_id: str
) -> dict[str, Any]:
    r = run_cmd(
        [
            sys.executable,
            str(CICD_ROOT / "scripts" / "agents" / "run-backend-sync-orchestrator.py"),
            "--dry-run",
            "--skip-deploy",
            "--lovable-dir",
            str(lovable),
            "--web-dir",
            str(web),
            "--back-dir",
            str(back),
            "--cicd-dir",
            str(CICD_ROOT),
            "--change-manifest",
            str(manifest),
            "--run-id",
            run_id,
        ],
        env={"DSF_AGENT_DRY_RUN": "1", "DSF_LOCAL_MODE": "1", "CICD_DIR": str(CICD_ROOT)},
        timeout=300,
    )
    summary_path = CICD_ROOT / "artifacts" / run_id / f"backend-sync-summary-{run_id}.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    return {
        "name": "bsf_orchestrator",
        "ok": r["ok"] and summary.get("ok", False),
        "steps": len(summary.get("steps") or []),
        "coupling": summary.get("couplingPercent"),
        "detail": r if not r["ok"] else {"steps": [s.get("step") for s in summary.get("steps", [])]},
    }


def test_load_secrets() -> dict[str, Any]:
    ps1 = CICD_ROOT / "scripts" / "load-dsf-secrets.ps1"
    if sys.platform != "win32":
        return {"name": "load_dsf_secrets", "ok": True, "skipped": "non-windows"}
    r = run_cmd(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         f". '{ps1}'; $r = Import-DsfSecrets -CicdRoot '{CICD_ROOT}'; $r | ConvertTo-Json"],
        timeout=30,
    )
    return {
        "name": "load_dsf_secrets",
        "ok": r["ok"],
        "hasKey": "CURSOR_API_KEY" in os.environ,
        "detail": r.get("stdout", "")[:500],
    }


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Validación multiagente DSF+BSF")
    parser.add_argument("--with-cursor", action="store_true", help="No forzar dry-run en implement")
    args = parser.parse_args()

    run_id = f"multiagent-{int(time.time())}"
    out = SIM_ROOT / "output" / "multiagent-validation" / run_id
    out.mkdir(parents=True, exist_ok=True)

    lovable = (SIM_ROOT / ".." / ".." / "discover-joyful-feed").resolve()
    web = (SIM_ROOT / ".." / ".." / "DoEventsWEB").resolve()
    back = (SIM_ROOT / ".." / ".." / "DoEventsBack").resolve()

    if not lovable.is_dir():
        lovable = (CICD_ROOT.parent / "discover-joyful-feed").resolve()
    if not web.is_dir():
        web = (CICD_ROOT.parent / "DoEventsWEB").resolve()

    manifest = make_simulated_manifest(out)

    # Copiar manifiesto simulado como principal para esta corrida
    os.environ["DSF_CHANGE_MANIFEST"] = str(manifest)

    tests: list[dict[str, Any]] = []
    tests.append(test_agent_scripts_exist())
    tests.append(test_backend_registry())
    tests.append(test_load_secrets())
    tests.append(test_delta_detector(lovable, web, manifest, run_id))
    tests.append(test_orchestrator_phases(lovable, web, f"{run_id}-pre", "pre-adapt", False))
    tests.append(test_orchestrator_phases(lovable, web, f"{run_id}-bsf", "backend-sync", True))
    tests.append(test_orchestrator_phases(lovable, web, f"{run_id}-all", "all", True))
    tests.append(test_bsf_orchestrator(lovable, web, back, manifest, run_id))

    passed = sum(1 for t in tests if t.get("ok"))
    failed = [t["name"] for t in tests if not t.get("ok")]

    report = {
        "runId": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "passed": passed,
        "total": len(tests),
        "allOk": not failed,
        "failed": failed,
        "tests": tests,
    }

    report_json = out / "validation-report.json"
    report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [
        "# Validación multiagente DSF + BSF",
        "",
        f"**Run:** `{run_id}` | **Resultado:** {'PASS' if report['allOk'] else 'FAIL'}",
        f"**Tests:** {passed}/{len(tests)}",
        "",
        "## Resultados",
        "",
    ]
    for t in tests:
        icon = "OK" if t.get("ok") else "FAIL"
        md_lines.append(f"- [{icon}] **{t['name']}**")
        if t.get("failedAgents"):
            md_lines.append(f"  - agentes fallidos: {t['failedAgents']}")
        if t.get("missing"):
            md_lines.append(f"  - faltantes: {t['missing']}")
    md_lines.extend(["", f"JSON: `{report_json}`"])
    md_path = out / "validation-report.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps({"allOk": report["allOk"], "passed": passed, "total": len(tests), "failed": failed}, indent=2))
    print(f"Reporte: {md_path}")
    return 0 if report["allOk"] else 1


if __name__ == "__main__":
    sys.exit(main())
