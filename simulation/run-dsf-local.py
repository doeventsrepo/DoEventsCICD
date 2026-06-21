#!/usr/bin/env python3
"""
Pipeline DSF local — itera sin disparar GitHub Actions ni deploy DEV.

Usa copia sandbox de DoEventsWEB (no toca el repo productivo por defecto).
Fases: init → prepare → gap → build → validate → report | all

Ejemplo (desde DoEventsCICD/simulation):
  python run-dsf-local.py init
  python run-dsf-local.py prepare
  python run-dsf-local.py gap
  python run-dsf-local.py build
  python run-dsf-local.py validate
  python run-dsf-local.py all
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parent
CICD_ROOT = SIM_ROOT.parent
SCRIPTS = CICD_ROOT / "scripts" / "lovable-sync"
SIM_SCRIPTS = SIM_ROOT / "scripts"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_local_config() -> dict:
    path = SIM_ROOT / "local.config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(path_str: str) -> Path:
    return (SIM_ROOT / path_str).resolve()


def run_id() -> str:
    return os.environ.get("DSF_LOCAL_RUN_ID", f"local-{int(datetime.now().timestamp())}")


def run_cmd(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, timeout: int = 3600) -> int:
    merged = {**os.environ, **(env or {})}
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=cwd, env=merged, timeout=timeout).returncode


def paths(cfg: dict) -> dict[str, Path]:
    repos = cfg["repos"]
    use_sandbox = cfg["modes"].get("useSandboxWeb", True) and not os.environ.get("DSF_LOCAL_USE_PRODUCTIVE_WEB")
    web = resolve(cfg["sandbox"]["web"]) if use_sandbox else resolve(repos["web"])
    out = resolve(cfg["sandbox"]["out"]) / run_id()
    out.mkdir(parents=True, exist_ok=True)
    return {
        "lovable": resolve(repos["lovable"]),
        "web": web,
        "back": resolve(repos["back"]),
        "cicd": resolve(repos["cicd"]),
        "out": out,
        "use_sandbox": use_sandbox,
    }


def load_env_file() -> None:
    env_path = SIM_ROOT / "local.env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def phase_init(cfg: dict) -> int:
    ps1 = SIM_ROOT / "prepare-sandbox.ps1"
    if sys.platform == "win32" and ps1.exists():
        return run_cmd(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)], cwd=SIM_ROOT)
    # fallback: avisar
    web_sandbox = resolve(cfg["sandbox"]["web"])
    if web_sandbox.exists():
        print(f"Sandbox ya existe: {web_sandbox}")
        return 0
    print("ERROR: Ejecuta prepare-sandbox.ps1 en Windows o copia DoEventsWEB a simulation/sandbox/DoEventsWEB")
    return 1


def phase_prepare(cfg: dict, p: dict[str, Path]) -> int:
    rc = 0
    rid = run_id()
    manifest = p["out"] / "lovable-change-manifest.json"
    design = p["out"] / "design-comparison.json"
    port_map = p["web"] / ".lovable-port-map.json"
    if not port_map.exists():
        port_map = CICD_ROOT / "templates" / ".lovable-port-map.json"

    if (p["lovable"] / "reglasActuacion").exists():
        rc = max(rc, run_cmd([sys.executable, str(SCRIPTS / "validate-rules.py"), "reglasActuacion"], cwd=p["lovable"]))

    if (p["lovable"] / "reglasDiseno").exists():
        rc = max(rc, run_cmd([sys.executable, str(SCRIPTS / "validate-design-rules.py"), "reglasDiseno"], cwd=p["lovable"]))

    rc = max(rc, run_cmd([sys.executable, str(SCRIPTS / "validate-agent-gate.py"), str(p["web"])]))
    rc = max(rc, run_cmd([sys.executable, str(SCRIPTS / "validate-reglas-cicd.py"), str(p["cicd"])]))

    diff_rc = run_cmd(
        [
            sys.executable,
            str(SCRIPTS / "analyze-lovable-diff.py"),
            str(p["lovable"]),
            "__last_sync__",
            "HEAD",
            str(p["web"]),
        ],
        cwd=p["lovable"],
        env={"CICD_WEB_BRANCH": "feature/cicd/dev-automation"},
    )
    rc = max(rc, diff_rc)
    src_manifest = p["lovable"] / "lovable-change-manifest.json"
    if src_manifest.exists():
        manifest.write_text(src_manifest.read_text(encoding="utf-8"), encoding="utf-8")

    rc = max(
        rc,
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "validate-port-map-coverage.py"),
                str(p["lovable"]),
                str(port_map),
                "--manifest",
                str(manifest),
                "--out",
                str(p["out"] / "port-map-result.json"),
            ],
        ),
    )

    rc = max(
        rc,
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "compare-design-similarity.py"),
                str(p["lovable"]),
                str(p["web"]),
                str(port_map),
                str(design),
            ],
        ),
    )

    ctx = p["lovable"] / ".ai" / "agent-sync-context.md"
    ctx.parent.mkdir(parents=True, exist_ok=True)
    if manifest.exists():
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "build-agent-context.py"),
                str(p["lovable"]),
                str(p["web"]),
                str(manifest),
                str(ctx),
            ],
            env={"CICD_DIR": str(p["cicd"]), "GITHUB_RUN_ID": rid},
        )
        run_cmd(
            [
                sys.executable,
                str(SCRIPTS / "generate-agent-artifacts.py"),
                str(p["lovable"]),
                str(p["web"]),
                str(manifest),
            ],
            env={"GITHUB_RUN_ID": rid, "BUILD_RESULT": "pending", "DSF_LOCAL_MODE": "1"},
        )

    summary = {}
    if design.exists():
        summary = json.loads(design.read_text(encoding="utf-8"))
    print(json.dumps({"phase": "prepare", "runId": rid, "similarity": summary.get("overallSimilarityPercent"), "sandbox": p["use_sandbox"]}, indent=2))
    return rc


def phase_empalme_local(p: dict[str, Path]) -> int:
    design = p["out"] / "design-comparison.json"
    if not design.exists():
        print("ERROR: ejecuta prepare antes de empalme", file=sys.stderr)
        return 1
    report = p["out"] / "local-empalme-report.json"
    return run_cmd(
        [
            sys.executable,
            str(SIM_SCRIPTS / "local-apply-empalme.py"),
            "--lovable-dir",
            str(p["lovable"]),
            "--web-dir",
            str(p["web"]),
            "--comparison",
            str(design),
            "--min-sim",
            "98",
            "--max-items",
            "120",
            "--out",
            str(report),
        ],
    )


def enforce_local_only(cfg: dict) -> None:
    """Bloquea cualquier contacto con GitHub / Cursor API en modo local."""
    if not cfg.get("modes", {}).get("blockGitHub", True):
        return
    for key in (
        "CURSOR_API_KEY",
        "DOEVENTS_WEB_PAT",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "SIM_RUN_LIVE_AGENT",
    ):
        if key in os.environ:
            print(f"BLOQUEO LOCAL: eliminando {key} del entorno (sin GitHub)", flush=True)
            os.environ.pop(key, None)
    os.environ["DSF_LOCAL_MODE"] = "1"
    os.environ["DSF_BLOCK_GITHUB"] = "1"


def phase_gap(cfg: dict, p: dict[str, Path], *, live_agent: bool) -> int:
    modes = cfg["modes"]
    if live_agent or modes.get("liveCursorAgent") or modes.get("allowCursorAgent"):
        print("ERROR: agente live/Cursor API deshabilitado en modo local (blockGitHub=true)", file=sys.stderr)
        return 1
    if modes.get("useLocalGapLoopOnly", True):
        design = p["out"] / "design-comparison.json"
        if not design.exists():
            print("ERROR: ejecuta prepare antes de gap", file=sys.stderr)
            return 1
        port_map = p["web"] / ".lovable-port-map.json"
        return run_cmd(
            [
                sys.executable,
                str(SIM_SCRIPTS / "local-gap-loop.py"),
                "--lovable-dir",
                str(p["lovable"]),
                "--web-dir",
                str(p["web"]),
                "--port-map",
                str(port_map),
                "--comparison",
                str(design),
                "--out-dir",
                str(p["out"]),
                "--target",
                str(modes.get("targetSimilarity", 98)),
                "--max-rounds",
                "5",
            ],
        )

    # Legacy (solo si useLocalGapLoopOnly=false explícitamente)
    port_map = p["web"] / ".lovable-port-map.json"
    env = {
        "CICD_DIR": str(p["cicd"]),
        "LOVABLE_DIR": str(p["lovable"]),
        "WEB_DIR": str(p["web"]),
        "AGENT_BRANCH": "feature/cicd/dev-automation",
        "DSF_LOCAL_MODE": "1",
    }
    cmd = [
        sys.executable,
        str(SCRIPTS / "dsf-gap-loop.py"),
        "--lovable-dir",
        str(p["lovable"]),
        "--web-dir",
        str(p["web"]),
        "--cicd-dir",
        str(p["cicd"]),
        "--port-map",
        str(port_map),
        "--target",
        str(modes.get("targetSimilarity", 98)),
        "--max-batches",
        str(modes.get("gapMaxBatches", 2)),
        "--batch-size",
        str(modes.get("gapBatchSize", 10)),
        "--run-id",
        run_id(),
    ]
    if not live_agent:
        cmd.append("--skip-agent")
        cmd.append("--analyze-only")
    elif not os.environ.get("CURSOR_API_KEY"):
        print("AVISO: sin CURSOR_API_KEY — gap en modo dry-run", file=sys.stderr)
        cmd.append("--skip-agent")
    else:
        print("AVISO: agente live empuja a GitHub (no sandbox). Usa sandbox solo para gates.", file=sys.stderr)
    rc = run_cmd(cmd, env=env)
    # Copiar artefactos gap al directorio del run local
    rid = run_id()
    for pattern in (f"gap-loop-summary-{rid}.json", f"gap-manifest-batch-*-{rid}.json", f"design-comparison-loop-*-{rid}.json"):
        for src in p["cicd"].glob(pattern):
            dest = p["out"] / src.name
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    final = p["cicd"] / f"design-comparison-loop-after-b2-{rid}.json"
    if not final.exists():
        for candidate in sorted(p["cicd"].glob(f"design-comparison-loop-after-*-{rid}.json")):
            final = candidate
    if final.exists():
        (p["out"] / "design-comparison-gap-final.json").write_text(final.read_text(encoding="utf-8"), encoding="utf-8")
    return rc


def phase_agent_dry(p: dict[str, Path]) -> int:
    manifest = p["out"] / "lovable-change-manifest.json"
    if not manifest.exists():
        manifest = p["lovable"] / "lovable-change-manifest.json"
    return run_cmd(
        [sys.executable, str(SIM_SCRIPTS / "simulate-agent-dry-run.py")],
        env={
            "CICD_DIR": str(p["cicd"]),
            "LOVABLE_DIR": str(p["lovable"]),
            "WEB_DIR": str(p["web"]),
            "MANIFEST_PATH": str(manifest),
            "SIM_OUTPUT_DIR": str(p["out"] / "agent-dry-run"),
        },
    )


def npm_cmd() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def phase_build(p: dict[str, Path]) -> int:
    if not (p["web"] / "package.json").exists():
        print("ERROR: package.json no encontrado en WEB", file=sys.stderr)
        return 1
    npm = npm_cmd()
    rc = run_cmd([npm, "ci"], cwd=p["web"], timeout=600)
    if rc != 0:
        return rc
    return run_cmd(
        [npm, "run", "build:devaws"],
        cwd=p["web"],
        env={"VITE_DOEVENTS_ENV": "devaws"},
        timeout=900,
    )


def phase_gates(cfg: dict, p: dict[str, Path]) -> int:
    rc = 0
    bash_candidates = [
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path("/usr/bin/bash"),
    ]
    bash = next((b for b in bash_candidates if b.exists()), None)
    if bash:
        rc = max(rc, run_cmd([str(bash), str(SCRIPTS / "validate-no-mocks.sh"), str(p["web"])]))
    else:
        print("AVISO: bash no encontrado; anti-mocks omitido", file=sys.stderr)
    rc = max(rc, run_cmd([sys.executable, str(CICD_ROOT / "scripts" / "rules" / "run-custom-gates.py"), str(p["cicd"] / "Reglas" / "custom"), "--web-dir", str(p["web"])]))
    return rc


def phase_validate(cfg: dict, p: dict[str, Path], *, deploy_ran: bool, smoke_ran: bool) -> int:
    design_before = p["out"] / "design-comparison.json"
    design_after = p["out"] / f"design-comparison-gap-final.json"
    if not design_after.exists():
        for candidate in sorted(p["out"].glob("design-comparison-loop-after-*.json")):
            design_after = candidate
    if not design_after.exists():
        design_after = design_before
    manifest = p["out"] / "lovable-change-manifest.json"
    validation_out = p["out"] / "validation-result.json"
    env_file = SIM_ROOT / "local.env"
    agent_ran = "true" if os.environ.get("SIM_RUN_LIVE_AGENT") == "1" else "false"
    return run_cmd(
        [
            sys.executable,
            str(SCRIPTS / "validate-pipeline-sync.py"),
            "--design-before",
            str(design_before),
            "--design-after",
            str(design_after),
            "--manifest",
            str(manifest),
            "--agent-ran",
            agent_ran,
            "--deploy-ran",
            "true" if deploy_ran else "false",
            "--smoke-ran",
            "true" if smoke_ran else "false",
            "--smoke-ok",
            "true" if smoke_ran else "false",
            "--cicd-dir",
            str(p["cicd"]),
            "--blocking",
            "false",
        ],
        env={"DSF_LOCAL_MODE": "1"},
    )


def phase_smoke_local(p: dict[str, Path]) -> int:
    shell_dist = p["web"] / "packages" / "shell" / "dist" / "index.html"
    mfe_dist = p["web"] / "packages" / "mfe-auth" / "dist" / "index.html"
    ok = shell_dist.exists() and mfe_dist.exists()
    result = {"ok": ok, "shell": str(shell_dist), "mfe_auth": str(mfe_dist), "mode": "local-artifacts"}
    out = p["out"] / "smoke-result-local.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if ok else 1


def phase_report(p: dict[str, Path]) -> int:
    rid = run_id()
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    md = p["out"] / f"{date}-dsf-local-{rid}.md"
    return run_cmd(
        [
            sys.executable,
            str(SCRIPTS / "generate-sync-report.py"),
            "--run-id",
            rid,
            "--manifest",
            str(p["out"] / "lovable-change-manifest.json"),
            "--design-before",
            str(p["out"] / "design-comparison.json"),
            "--design-after",
            str(p["out"] / "design-comparison.json"),
            "--validation",
            str(p["out"] / "validation-result.json"),
            "--smoke",
            str(p["out"] / "smoke-result-local.json"),
            "--port-map",
            str(p["out"] / "port-map-result.json"),
            "--out-md",
            str(md),
            "--out-json",
            str(p["out"] / f"{date}-dsf-local-{rid}.json"),
        ],
    )


def main() -> int:
    load_env_file()
    cfg = load_local_config()
    enforce_local_only(cfg)
    parser = argparse.ArgumentParser(description="DSF pipeline local (sin CI/CD remoto)")
    parser.add_argument(
        "phase",
        choices=["init", "prepare", "empalme", "gap", "agent-dry", "build", "gates", "smoke", "validate", "report", "all"],
    )
    parser.add_argument("--live-agent", action="store_true", help="Gap con Cursor API (empuja a GitHub)")
    parser.add_argument("--deploy", action="store_true", help="Deploy AWS DEV (requiere credenciales)")
    parser.add_argument("--remote-smoke", action="store_true", help="Smoke contra api-dev.doeventsapp.com")
    args = parser.parse_args()

    cfg = load_local_config()
    enforce_local_only(cfg)
    p = paths(cfg)
    print(f"DSF LOCAL | run={run_id()} | sandbox_web={p['use_sandbox']} | out={p['out']}")

    if args.phase == "init":
        return phase_init(cfg)

    if args.phase == "prepare":
        return phase_prepare(cfg, p)

    if args.phase == "empalme":
        return phase_empalme_local(p)

    if args.live_agent:
        print("ERROR: --live-agent no permitido (blockGitHub=true). Usa solo sandbox local.", file=sys.stderr)
        return 1

    if args.phase == "gap":
        return phase_gap(cfg, p, live_agent=False)

    if args.phase == "agent-dry":
        return phase_agent_dry(p)

    if args.phase == "build":
        return phase_build(p)

    if args.phase == "gates":
        return phase_gates(cfg, p)

    if args.phase == "smoke":
        if args.remote_smoke and cfg["modes"].get("allowRemoteSmoke", False):
            return run_cmd(["bash", str(CICD_ROOT / "scripts" / "smoke" / "dev-smoke.sh"), str(p["out"] / "smoke-result.json")])
        return phase_smoke_local(p)

    if args.phase == "validate":
        built = (p["web"] / "packages" / "shell" / "dist" / "index.html").exists()
        return phase_validate(cfg, p, deploy_ran=args.deploy, smoke_ran=built)

    if args.phase == "report":
        return phase_report(p)

    # all
    rc = 0
    if not p["web"].exists():
        rc = max(rc, phase_init(cfg))
    rc = max(rc, phase_prepare(cfg, p))
    rc = max(rc, phase_empalme_local(p))
    # Re-medir tras empalme local
    phase_prepare(cfg, p)
    rc = max(rc, phase_agent_dry(p))
    # Orquestador multi-agente (pre/post adapt, sin API)
    rc = max(
        rc,
        run_cmd(
            [
                sys.executable,
                str(p["cicd"] / "scripts" / "agents" / "orchestrator.py"),
                "--dry-run",
                "--phase",
                "all",
                "--skip-adapt",
                "--lovable-dir",
                str(p["lovable"]),
                "--web-dir",
                str(p["web"]),
                "--design-comparison",
                str(p["out"] / "design-comparison.json"),
            ],
            env={"DSF_LOCAL_RUN_ID": run_id(), "CICD_DIR": str(p["cicd"])},
        ),
    )
    rc = max(rc, phase_gap(cfg, p, live_agent=False))
    rc = max(rc, phase_gates(cfg, p))
    rc = max(rc, phase_build(p))
    smoke_rc = phase_smoke_local(p)
    rc = max(rc, smoke_rc)
    if args.deploy and cfg["modes"].get("allowAwsDeploy"):
        rc = max(rc, run_cmd(["bash", str(CICD_ROOT / "scripts" / "deploy" / "providers" / "aws-deploy.sh"), str(p["web"]), "dev"]))
    phase_validate(cfg, p, deploy_ran=args.deploy, smoke_ran=smoke_rc == 0)
    phase_report(p)
    print(f"\nInforme en: {p['out']}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
