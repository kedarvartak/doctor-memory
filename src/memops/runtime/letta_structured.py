from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from memops.core.events import EventKind, utc_now_iso
from memops.runtime.letta_runtime import AGENT_ID_ENV, SESSION_ID_ENV, STRUCTURED_TRACE_PATH_ENV


def emit_structured_retrieval(
    *,
    query: str,
    memory_id: str | None = None,
    related_memory_ids: list[str] | None = None,
    latency_ms: float | None = None,
    tokens_loaded: int | None = None,
    score: float | None = None,
    used: bool | None = None,
    stale: bool | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    output_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "event_id": f"{session_id or os.environ.get(SESSION_ID_ENV, 'session')}:{utc_now_iso()}",
        "kind": EventKind.MEMORY_RETRIEVED.value,
        "framework": "letta",
        "agent_id": agent_id or os.environ.get(AGENT_ID_ENV, ""),
        "session_id": session_id or os.environ.get(SESSION_ID_ENV, ""),
        "timestamp": utc_now_iso(),
        "source": "letta-structured-runtime",
        "memory_id": memory_id,
        "related_memory_ids": list(related_memory_ids or []),
        "query": query,
        "metadata": {
            **(metadata or {}),
            **({"used": used} if used is not None else {}),
            **({"stale": stale} if stale is not None else {}),
            "structured": True,
        },
        "latency_ms": latency_ms,
        "tokens_loaded": tokens_loaded,
        "score": score,
    }
    return _append_payload(payload, output_path=output_path)


def emit_structured_retrieval_miss(
    *,
    query: str,
    reason: str | None = None,
    latency_ms: float | None = None,
    agent_id: str | None = None,
    session_id: str | None = None,
    output_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "event_id": f"{session_id or os.environ.get(SESSION_ID_ENV, 'session')}:{utc_now_iso()}",
        "kind": EventKind.MEMORY_RETRIEVAL_MISS.value,
        "framework": "letta",
        "agent_id": agent_id or os.environ.get(AGENT_ID_ENV, ""),
        "session_id": session_id or os.environ.get(SESSION_ID_ENV, ""),
        "timestamp": utc_now_iso(),
        "source": "letta-structured-runtime",
        "query": query,
        "metadata": {
            **(metadata or {}),
            **({"reason": reason} if reason else {}),
            "structured": True,
        },
        "latency_ms": latency_ms,
    }
    return _append_payload(payload, output_path=output_path)


def _append_payload(payload: dict[str, Any], *, output_path: str | Path | None = None) -> Path:
    path = Path(output_path or os.environ.get(STRUCTURED_TRACE_PATH_ENV, "")).expanduser()
    if not str(path):
        raise RuntimeError("Structured trace output path is not configured.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return path
