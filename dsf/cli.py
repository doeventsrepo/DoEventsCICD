#!/usr/bin/env python3
"""DSF CLI — punto de entrada unificado para sync, deploy y validación."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from dsf.config import load_config, qa_promotion_enabled


def root() -> Path:
    return Path(__file__).resolve().parent.parent


def cmd_config(_: argparse.Namespace) -> int:
    cfg = load_config(root())
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    cicd = root()
    scripts = cicd / "scripts" / "lovable-sync"
    rc = 0
    if args.mocks:
        r = subprocess.run(["bash", str(scripts / "validate-no-mocks.sh"), args.web_dir])
        rc = max(rc, r.returncode)
    if args.port_map:
        r = subprocess.run([
            sys.executable, str(scripts / "validate-port-map-coverage.py"),
            args.lovable_dir, args.port_map,
        ])
        rc = max(rc, r.returncode)
    return rc


def cmd_deploy(args: argparse.Namespace) -> int:
    cfg = load_config(root())
    provider = args.provider or cfg.get("cloud", {}).get("defaultProvider", "aws")
    script = root() / "scripts" / "deploy" / "providers" / f"{provider}-deploy.sh"
    if not script.exists():
        print(f"ERROR: provider no soportado: {provider}", file=sys.stderr)
        return 1
    env = {**dict(subprocess.os.environ), "DSF_ENV": args.env, "DSF_WEB_DIR": args.web_dir}
    return subprocess.run(["bash", str(script), args.web_dir, args.env], env=env).returncode


def cmd_promote_qa(_: argparse.Namespace) -> int:
    cfg = load_config(root())
    if not qa_promotion_enabled(cfg):
        reason = cfg.get("dsf", {}).get("qaPromotion", {}).get("reason", "QA inhabilitado")
        print(f"ERROR: Promoción QA inhabilitada — {reason}", file=sys.stderr)
        return 1
    print("Promoción QA habilitada en config — ejecutar workflow dsf-promote-qa.yml")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    script = root() / "scripts" / "smoke" / "dev-smoke.sh"
    return subprocess.run(["bash", str(script), args.out or "/tmp/dsf-smoke.json"]).returncode


def main() -> int:
    parser = argparse.ArgumentParser(prog="dsf", description="Design Sync Framework CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cfg = sub.add_parser("config", help="Mostrar cicd.config.json")
    p_cfg.set_defaults(func=cmd_config)

    p_val = sub.add_parser("validate", help="Ejecutar gates locales")
    p_val.add_argument("--web-dir", default=".")
    p_val.add_argument("--lovable-dir", default="../discover-joyful-feed")
    p_val.add_argument("--port-map", default=".lovable-port-map.json")
    p_val.add_argument("--mocks", action="store_true", default=True)
    p_val.add_argument("--port-map-check", dest="port_map", action="store_true")
    p_val.set_defaults(func=cmd_validate)

    p_dep = sub.add_parser("deploy", help="Desplegar vía provider cloud")
    p_dep.add_argument("--env", default="dev", choices=["dev", "qa", "prod"])
    p_dep.add_argument("--provider", default="")
    p_dep.add_argument("--web-dir", default=".")
    p_dep.set_defaults(func=cmd_deploy)

    p_sm = sub.add_parser("smoke", help="Smoke tests DEV")
    p_sm.add_argument("--out", default="")
    p_sm.set_defaults(func=cmd_smoke)

    p_qa = sub.add_parser("promote-qa", help="Promover a QA (solo si habilitado)")
    p_qa.set_defaults(func=cmd_promote_qa)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
