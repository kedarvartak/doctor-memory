from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from memfs_doctor.core.events import EventKind, MemoryEvent


LOW_SCORE_THRESHOLD = 0.8


@dataclass(slots=True)
class RetrievalTrace:
    step: int
    event_id: str
    kind: str
    timestamp: str
    query: str | None
    memory_id: str | None
    related_memory_ids: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    tokens_loaded: int | None = None
    score: float | None = None
    used: bool | None = None
    stale: bool = False
    likely_useful: bool = False
    likely_noisy: bool = False
    cause_step: int | None = None
    cause_event_id: str | None = None
    cause_kind: str | None = None
    cause_summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievalInspectionReport:
    session_id: str
    framework: str
    agent_id: str
    traces: list[RetrievalTrace] = field(default_factory=list)

    @property
    def retrieval_count(self) -> int:
        return sum(1 for trace in self.traces if trace.kind == EventKind.MEMORY_RETRIEVED.value)

    @property
    def miss_count(self) -> int:
        return sum(1 for trace in self.traces if trace.kind == EventKind.MEMORY_RETRIEVAL_MISS.value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "framework": self.framework,
            "agent_id": self.agent_id,
            "retrieval_count": self.retrieval_count,
            "miss_count": self.miss_count,
            "top_problematic_recalls": [item.to_dict() for item in top_problematic_recalls(self.traces)],
            "top_token_pressure_recalls": [item.to_dict() for item in top_token_pressure_recalls(self.traces)],
            "traces": [trace.to_dict() for trace in self.traces],
        }


def analyze_retrievals(events: list[MemoryEvent]) -> RetrievalInspectionReport:
    if not events:
        raise ValueError("Cannot analyze retrievals for an empty event list.")

    latest_write_by_memory: dict[str, tuple[int, MemoryEvent]] = {}
    traces: list[RetrievalTrace] = []

    for step, event in enumerate(events, start=1):
        if event.kind in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED, EventKind.MEMORY_DELETED} and event.memory_id:
            latest_write_by_memory[event.memory_id] = (step, event)

        if event.kind not in {EventKind.MEMORY_RETRIEVED, EventKind.MEMORY_RETRIEVAL_MISS}:
            continue

        used = event.metadata.get("used")
        stale = bool(event.metadata.get("stale"))
        inferred = bool(event.metadata.get("inferred"))
        cause_step = None
        cause_event_id = None
        cause_kind = None
        cause_summary = None
        if event.memory_id and event.memory_id in latest_write_by_memory:
            linked_step, linked_event = latest_write_by_memory[event.memory_id]
            cause_step = linked_step
            cause_event_id = linked_event.event_id
            cause_kind = linked_event.kind.value
            cause_summary = summarize_memory_event(linked_event)

        likely_useful = (
            event.kind == EventKind.MEMORY_RETRIEVED
            and not stale
            and (
                used is True
                or (not inferred and event.memory_id is not None)
            )
        )
        likely_noisy = event.kind == EventKind.MEMORY_RETRIEVED and (
            stale
            or used is False
            or (event.score is not None and event.score < LOW_SCORE_THRESHOLD)
            or (inferred and inferred_recall_looks_noisy(event))
        )

        traces.append(
            RetrievalTrace(
                step=step,
                event_id=event.event_id,
                kind=event.kind.value,
                timestamp=event.timestamp,
                query=event.query,
                memory_id=event.memory_id,
                related_memory_ids=list(event.related_memory_ids),
                latency_ms=event.latency_ms,
                tokens_loaded=event.tokens_loaded,
                score=event.score,
                used=bool(used) if isinstance(used, bool) else None,
                stale=stale,
                likely_useful=likely_useful,
                likely_noisy=likely_noisy,
                cause_step=cause_step,
                cause_event_id=cause_event_id,
                cause_kind=cause_kind,
                cause_summary=cause_summary,
                metadata=dict(event.metadata),
            )
        )

    return RetrievalInspectionReport(
        session_id=events[0].session_id,
        framework=events[0].framework,
        agent_id=events[0].agent_id,
        traces=traces,
    )


def retrieval_trace_for_step(events: list[MemoryEvent], step: int) -> RetrievalTrace:
    report = analyze_retrievals(events)
    for trace in report.traces:
        if trace.step == step:
            return trace
    raise ValueError(f"No retrieval event found at step {step}")


def top_problematic_recalls(traces: list[RetrievalTrace], limit: int = 3) -> list[RetrievalTrace]:
    problematic = [
        trace
        for trace in traces
        if trace.kind == EventKind.MEMORY_RETRIEVED.value and (trace.stale or trace.likely_noisy)
    ]
    return sorted(problematic, key=_problematic_sort_key, reverse=True)[:limit]


def top_token_pressure_recalls(traces: list[RetrievalTrace], limit: int = 3) -> list[RetrievalTrace]:
    retrievals = [trace for trace in traces if trace.kind == EventKind.MEMORY_RETRIEVED.value]
    return sorted(
        retrievals,
        key=lambda trace: (trace.tokens_loaded or 0, trace.latency_ms or 0.0, trace.step),
        reverse=True,
    )[:limit]


def summarize_memory_event(event: MemoryEvent) -> str:
    payload = event.after or event.before or {}
    content = str(payload.get("content", "")).strip()
    if content:
        compact = " ".join(content.split())
        return compact[:120]
    subject = event.metadata.get("subject")
    if isinstance(subject, str) and subject.strip():
        return subject.strip()
    return event.kind.value


def _problematic_sort_key(trace: RetrievalTrace) -> tuple[int, int, float, float, int]:
    return (
        1 if trace.stale else 0,
        1 if trace.likely_noisy else 0,
        trace.tokens_loaded or 0,
        trace.latency_ms or 0.0,
        trace.step,
    )


def inferred_recall_looks_noisy(event: MemoryEvent) -> bool:
    response_text = str(event.metadata.get("response_text", "")).strip().lower()
    if not response_text:
        return True
    if event.memory_id is None and len(response_text) > 240:
        return True
    noisy_markers = (
        "session usage:",
        "resume this agent with:",
        "/agents",
        "/resume",
        "total duration (api):",
        "total duration (wall):",
        "letta code is ",
    )
    return any(marker in response_text for marker in noisy_markers)
