from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memfs_doctor.core.events import EventKind, MemoryEvent


@dataclass(slots=True)
class MetricsReport:
    session_id: str
    framework: str
    agent_id: str
    values: dict[str, Any] = field(default_factory=dict)


def _duplicate_rate(events: list[MemoryEvent]) -> float:
    seen_contents: dict[str, int] = {}
    duplicate_count = 0
    created_or_updated = 0
    for event in events:
        if event.kind not in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED}:
            continue
        created_or_updated += 1
        content = ""
        if event.after:
            content = str(event.after.get("content", "")).strip().lower()
        if not content:
            continue
        if content in seen_contents:
            duplicate_count += 1
        seen_contents[content] = seen_contents.get(content, 0) + 1
    if created_or_updated == 0:
        return 0.0
    return round(duplicate_count / created_or_updated, 4)


def _contradiction_score(events: list[MemoryEvent]) -> float:
    values_by_key: dict[str, set[str]] = {}
    for event in events:
        if event.kind not in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED} or not event.after:
            continue
        attributes = event.after.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        for key, value in attributes.items():
            values_by_key.setdefault(str(key), set()).add(str(value).strip().lower())
    contradictions = sum(1 for values in values_by_key.values() if len(values) > 1)
    keys = len(values_by_key)
    if keys == 0:
        return 0.0
    return round(contradictions / keys, 4)


def _stale_recall_rate(events: list[MemoryEvent]) -> float:
    retrievals = 0
    stale = 0
    for event in events:
        if event.kind != EventKind.MEMORY_RETRIEVED:
            continue
        retrievals += 1
        if bool(event.metadata.get("stale")):
            stale += 1
    if retrievals == 0:
        return 0.0
    return round(stale / retrievals, 4)


def compute_metrics(events: list[MemoryEvent]) -> MetricsReport:
    if not events:
        raise ValueError("Cannot compute metrics for an empty event list.")

    retrievals = [event for event in events if event.kind == EventKind.MEMORY_RETRIEVED]
    retrieval_misses = [event for event in events if event.kind == EventKind.MEMORY_RETRIEVAL_MISS]
    writes = [
        event
        for event in events
        if event.kind in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED, EventKind.MEMORY_DELETED}
    ]

    total_latency = sum(event.latency_ms or 0.0 for event in retrievals)
    total_tokens = sum(event.tokens_loaded or 0 for event in retrievals)
    empty_retrieval_rate = 0.0
    retrieval_denominator = len(retrievals) + len(retrieval_misses)
    if retrieval_denominator:
        empty_retrieval_rate = round(len(retrieval_misses) / retrieval_denominator, 4)

    context_pressure = round(total_tokens / max(len(retrievals), 1), 2) if retrievals else 0.0
    avg_latency = round(total_latency / len(retrievals), 2) if retrievals else 0.0

    return MetricsReport(
        session_id=events[0].session_id,
        framework=events[0].framework,
        agent_id=events[0].agent_id,
        values={
            "event_count": len(events),
            "write_count": len(writes),
            "retrieval_count": len(retrievals),
            "retrieval_latency_ms_avg": avg_latency,
            "memory_tokens_loaded_total": total_tokens,
            "context_pressure_score": context_pressure,
            "memory_churn_rate": round(len(writes) / max(len(events), 1), 4),
            "duplicate_rate": _duplicate_rate(events),
            "contradiction_score": _contradiction_score(events),
            "stale_recall_rate": _stale_recall_rate(events),
            "empty_retrieval_rate": empty_retrieval_rate,
        },
    )

