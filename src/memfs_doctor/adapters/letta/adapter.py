from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from memfs_doctor.adapters.base import AdapterError, BaseAdapter
from memfs_doctor.core.events import EventKind, MemoryEvent, utc_now_iso


LETTA_KIND_MAP = {
    "session_started": EventKind.SESSION_STARTED,
    "session_ended": EventKind.SESSION_ENDED,
    "memory_created": EventKind.MEMORY_CREATED,
    "memory_updated": EventKind.MEMORY_UPDATED,
    "memory_deleted": EventKind.MEMORY_DELETED,
    "memory_retrieved": EventKind.MEMORY_RETRIEVED,
    "memory_retrieval_miss": EventKind.MEMORY_RETRIEVAL_MISS,
    "summary_generated": EventKind.SUMMARY_GENERATED,
    "compaction_run": EventKind.COMPACTION_RUN,
}


class LettaTraceAdapter(BaseAdapter):
    framework = "letta"

    def load_events(self, path: str | Path) -> list[MemoryEvent]:
        trace_path = Path(path)
        if not trace_path.exists():
            raise AdapterError(f"Trace file does not exist: {trace_path}")

        events: list[MemoryEvent] = []
        with trace_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise AdapterError(f"Invalid JSON on line {line_number}: {exc}") from exc
                events.append(self._normalize(payload, line_number))
        return events

    def _normalize(self, payload: dict[str, Any], line_number: int) -> MemoryEvent:
        kind_value = payload.get("kind") or payload.get("event_type")
        if kind_value not in LETTA_KIND_MAP:
            raise AdapterError(f"Unsupported Letta event kind on line {line_number}: {kind_value!r}")

        framework = payload.get("framework", self.framework)
        session_id = payload.get("session_id")
        agent_id = payload.get("agent_id")
        event_id = payload.get("event_id") or f"{session_id}:{line_number}"
        if not session_id or not agent_id:
            raise AdapterError(f"Missing session_id or agent_id on line {line_number}")

        return MemoryEvent(
            event_id=event_id,
            kind=LETTA_KIND_MAP[kind_value],
            framework=framework,
            agent_id=agent_id,
            session_id=session_id,
            timestamp=payload.get("timestamp", utc_now_iso()),
            source=payload.get("source", "letta-trace"),
            memory_id=payload.get("memory_id"),
            related_memory_ids=list(payload.get("related_memory_ids", [])),
            query=payload.get("query"),
            before=payload.get("before"),
            after=payload.get("after"),
            metadata=dict(payload.get("metadata", {})),
            latency_ms=payload.get("latency_ms"),
            tokens_loaded=payload.get("tokens_loaded"),
            score=payload.get("score"),
        )

