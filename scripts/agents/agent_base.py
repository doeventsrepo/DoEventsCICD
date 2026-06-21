#!/usr/bin/env python3
"""Utilidades compartidas para agentes DSF (Cursor API + dry-run local)."""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_CICD = Path(__file__).resolve().parents[2]


def cicd_root() -> Path:
    env = os.environ.get("CICD_DIR")
    return Path(env).resolve() if env else DEFAULT_CICD


def load_config() -> dict[str, Any]:
    path = cicd_root() / "cicd.config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def dsf_core(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    return cfg.get("dsfCore", {})


def artifacts_dir(run_id: str | None = None) -> Path:
    rid = run_id or os.environ.get("GITHUB_RUN_ID", os.environ.get("DSF_LOCAL_RUN_ID", "local"))
    out = cicd_root() / "artifacts" / str(rid)
    out.mkdir(parents=True, exist_ok=True)
    return out


def is_dry_run() -> bool:
    return os.environ.get("DSF_AGENT_DRY_RUN", "0") == "1" or os.environ.get("DSF_LOCAL_MODE", "0") == "1"


def is_local_mode() -> bool:
    return os.environ.get("DSF_LOCAL_MODE", "0") == "1" or os.environ.get("DSF_BLOCK_GITHUB", "0") == "1"


def gh_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{name}={value}\n")


def write_report(name: str, data: dict[str, Any], run_id: str | None = None) -> Path:
    out = artifacts_dir(run_id) / name
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def read_optional(path: Path | str) -> str:
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def cursor_api(method: str, path: str, body: dict | None = None, api_base: str | None = None) -> dict:
    key = os.environ.get("CURSOR_API_KEY", "")
    if not key:
        raise RuntimeError("CURSOR_API_KEY requerido")
    base = (api_base or "https://api.cursor.com/v1/agents").rstrip("/")
    url = f"{base}{path}" if path.startswith("/") else (base if not path else f"{base}/{path}")
    data = json.dumps(body).encode() if body is not None else None
    basic = base64.b64encode(f"{key}:".encode()).decode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def invoke_cursor_agent(
    *,
    name: str,
    prompt_text: str,
    repos: list[dict[str, str]] | None = None,
    wait: bool = False,
    model: str = "composer-2.5",
) -> dict[str, Any]:
    if is_dry_run() or not os.environ.get("CURSOR_API_KEY"):
        preview = {
            "dryRun": True,
            "name": name,
            "promptChars": len(prompt_text),
            "repos": repos or [],
            "model": model,
        }
        write_report("cursor-agent-dry-run.json", preview)
        return preview

    payload = {
        "prompt": {"text": prompt_text},
        "model": {"id": os.environ.get("CURSOR_AGENT_MODEL", model)},
        "repos": repos or [],
        "workOnCurrentBranch": True,
        "autoCreatePR": False,
        "skipReviewerRequest": True,
        "name": name,
    }
    created = cursor_api("POST", "", payload)
    agent = created.get("agent") or {}
    run = created.get("run") or {}
    agent_id = agent.get("id") or created.get("id")
    run_id = run.get("id") or agent.get("latestRunId")

    result: dict[str, Any] = {"agentId": agent_id, "runId": run_id, "url": agent.get("url", "")}

    if wait and agent_id and run_id:
        deadline = time.time() + int(os.environ.get("AGENT_POLL_TIMEOUT", "1800"))
        while time.time() < deadline:
            state = cursor_api("GET", f"/{agent_id}/runs/{run_id}")
            status = (state.get("status") or "").upper()
            if status in {"FINISHED", "ERROR", "CANCELLED", "CANCELED", "EXPIRED"}:
                result["status"] = status
                result["final"] = state
                break
            time.sleep(int(os.environ.get("AGENT_POLL_INTERVAL", "20")))
    write_report("cursor-agent-result.json", result)
    return result


def run_subprocess_script(script_rel: str, extra_args: list[str] | None = None, env: dict | None = None) -> int:
    script = cicd_root() / script_rel
    if not script.exists():
        print(f"ERROR: script no encontrado: {script}", file=sys.stderr)
        return 1
    merged = {**os.environ, **(env or {})}
    import subprocess

    cmd = [sys.executable, str(script), *(extra_args or [])]
    return subprocess.run(cmd, env=merged).returncode
