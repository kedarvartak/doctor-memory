from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import json
from typing import Any


class EventKind(StrEnum):
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_RETRIEVAL_MISS = "memory_retrieval_miss"
    SUMMARY_GENERATED = "summary_generated"
    COMPACTION_RUN = "compaction_run"


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def normalize_iso_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


@dataclass(slots=True)
class MemoryEvent:
    event_id: str
    kind: EventKind
    framework: str
    agent_id: str
    session_id: str
    timestamp: str
    source: str
    memory_id: str | None = None
    related_memory_ids: list[str] = field(default_factory=list)
    query: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    latency_ms: float | None = None
    tokens_loaded: int | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        self.timestamp = normalize_iso_timestamp(self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["kind"] = self.kind.value
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryEvent":
        return cls(
            event_id=payload["event_id"],
            kind=EventKind(payload["kind"]),
            framework=payload["framework"],
            agent_id=payload["agent_id"],
            session_id=payload["session_id"],
            timestamp=payload.get("timestamp", utc_now_iso()),
            source=payload.get("source", payload["framework"]),
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


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    framework: str
    agent_id: str
    started_at: str | None = None
    ended_at: str | None = None
    event_count: int = 0
