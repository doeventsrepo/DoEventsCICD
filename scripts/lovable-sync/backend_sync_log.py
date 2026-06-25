#!/usr/bin/env python3
"""Logging estructurado BSF — JSONL para agente healer y reportes."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LOG = "backend-sync/errors.jsonl"


def _log_path(run_id: str | None = None) -> Path:
    from agent_base import artifacts_dir, cicd_root

    rid = run_id or os.environ.get("GITHUB_RUN_ID", os.environ.get("DSF_LOCAL_RUN_ID", "local"))
    out = artifacts_dir(rid) / "backend-sync"
    out.mkdir(parents=True, exist_ok=True)
    return out / "errors.jsonl"


def append_log(
    event: str,
    *,
    level: str = "info",
    message: str = "",
    domain: str | None = None,
    lambda_dir: str | None = None,
    error: str | None = None,
    fix_applied: bool = False,
    fix_summary: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> Path:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "level": level,
        "message": message,
        "domain": domain,
        "lambdaDir": lambda_dir,
        "error": error,
        "fixApplied": fix_applied,
        "fixSummary": fix_summary,
        "metadata": metadata or {},
    }
    path = _log_path(run_id)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def read_logs(run_id: str | None = None, level: str | None = None) -> list[dict[str, Any]]:
    path = _log_path(run_id)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if level and row.get("level") != level:
            continue
        rows.append(row)
    return rows
