from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from memops.core.events import EventKind, MemoryEvent


@dataclass(slots=True)
class MemorySnapshot:
    session_id: str
    step: int
    memories: dict[str, dict[str, Any]] = field(default_factory=dict)


def apply_event(snapshot: MemorySnapshot, event: MemoryEvent) -> None:
    if event.kind == EventKind.MEMORY_CREATED and event.memory_id and event.after:
        snapshot.memories[event.memory_id] = dict(event.after)
        return

    if event.kind == EventKind.MEMORY_UPDATED and event.memory_id:
        current = snapshot.memories.get(event.memory_id, {})
        merged = dict(current)
        if event.after:
            merged.update(event.after)
        snapshot.memories[event.memory_id] = merged
        return

    if event.kind == EventKind.MEMORY_DELETED and event.memory_id:
        snapshot.memories.pop(event.memory_id, None)


def build_snapshot(session_id: str, events: list[MemoryEvent], step: int | None = None) -> MemorySnapshot:
    snapshot = MemorySnapshot(session_id=session_id, step=0)
    max_index = len(events) if step is None else max(0, min(step, len(events)))
    for index, event in enumerate(events[:max_index], start=1):
        apply_event(snapshot, event)
        snapshot.step = index
    return snapshot


def diff_snapshots(before: MemorySnapshot, after: MemorySnapshot) -> dict[str, list[str]]:
    before_ids = set(before.memories)
    after_ids = set(after.memories)

    created = sorted(after_ids - before_ids)
    deleted = sorted(before_ids - after_ids)
    updated = sorted(
        memory_id
        for memory_id in before_ids & after_ids
        if before.memories[memory_id] != after.memories[memory_id]
    )
    return {"created": created, "updated": updated, "deleted": deleted}

