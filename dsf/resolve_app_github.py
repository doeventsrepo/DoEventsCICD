#!/usr/bin/env python3
"""Emite outputs key=value para GitHub Actions desde el registro de aplicaciones."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dsf.app_resolver import application_env, resolve_application


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", default="", help="ID en applications.registry")
    parser.add_argument("--cicd-dir", default=".")
    args = parser.parse_args()

    cicd_root = Path(args.cicd_dir).resolve()
    app = resolve_application(args.app_id or None, cicd_root=cicd_root)
    env = application_env(app)

    if os_mode_github_output():
        out_path = Path(os.environ["GITHUB_OUTPUT"])
        with out_path.open("a", encoding="utf-8") as fh:
            for key, value in env.items():
                fh.write(f"{key}={value}\n")
    else:
        for key, value in env.items():
            print(f"{key}={value}")

    return 0


def os_mode_github_output() -> bool:
    import os

    return "GITHUB_OUTPUT" in os.environ


if __name__ == "__main__":
    sys.exit(main())
