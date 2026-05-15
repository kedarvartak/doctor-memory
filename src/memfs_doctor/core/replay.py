from __future__ import annotations

from dataclasses import dataclass

from memfs_doctor.core.events import EventKind, MemoryEvent
from memfs_doctor.core.snapshots import build_snapshot, diff_snapshots


@dataclass(slots=True)
class ReplayTimelineEntry:
    step: int
    timestamp: str
    kind: str
    memory_id: str | None
    query: str | None
    summary: str
    snapshot_memory_count: int
    flags: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "memory_id": self.memory_id,
            "query": self.query,
            "summary": self.summary,
            "snapshot_memory_count": self.snapshot_memory_count,
            "flags": list(self.flags),
        }


@dataclass(slots=True)
class StepInspection:
    session_id: str
    step: int
    total_steps: int
    summary: str
    event: dict[str, object]
    snapshot: dict[str, dict[str, object]]
    delta_from_previous: dict[str, object]
    flags: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "step": self.step,
            "total_steps": self.total_steps,
            "summary": self.summary,
            "event": self.event,
            "snapshot": self.snapshot,
            "delta_from_previous": self.delta_from_previous,
            "flags": list(self.flags),
        }


@dataclass(slots=True)
class ReplayResult:
    session_id: str
    total_steps: int
    issue_first_seen: dict[str, int | None]
    timeline: list[ReplayTimelineEntry]
    final_snapshot_memory_count: int
    final_memory_ids: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "total_steps": self.total_steps,
            "issue_first_seen": dict(self.issue_first_seen),
            "final_snapshot_memory_count": self.final_snapshot_memory_count,
            "final_memory_ids": list(self.final_memory_ids),
            "timeline": [entry.to_dict() for entry in self.timeline],
        }


def find_first_duplicate_event(events: list[MemoryEvent]) -> int | None:
    seen_contents: set[str] = set()
    for index, event in enumerate(events, start=1):
        if event.kind not in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED} or not event.after:
            continue
        content = str(event.after.get("content", "")).strip().lower()
        if not content:
            continue
        if content in seen_contents:
            return index
        seen_contents.add(content)
    return None


def find_first_contradiction_event(events: list[MemoryEvent]) -> int | None:
    values_by_key: dict[str, set[str]] = {}
    for index, event in enumerate(events, start=1):
        if event.kind not in {EventKind.MEMORY_CREATED, EventKind.MEMORY_UPDATED} or not event.after:
            continue
        attributes = event.after.get("attributes", {})
        if not isinstance(attributes, dict):
            continue
        for key, value in attributes.items():
            normalized_key = str(key)
            normalized_value = str(value).strip().lower()
            values = values_by_key.setdefault(normalized_key, set())
            if values and normalized_value not in values:
                return index
            values.add(normalized_value)
    return None


def summarize_event(event: MemoryEvent) -> str:
    target = event.memory_id or "-"
    if event.kind == EventKind.MEMORY_CREATED:
        return f"created {target}"
    if event.kind == EventKind.MEMORY_UPDATED:
        return f"updated {target}"
    if event.kind == EventKind.MEMORY_DELETED:
        return f"deleted {target}"
    if event.kind == EventKind.MEMORY_RETRIEVED:
        return f"retrieved {target} for {event.query!r}" if event.query else f"retrieved {target}"
    if event.kind == EventKind.MEMORY_RETRIEVAL_MISS:
        return f"retrieval miss for {event.query!r}" if event.query else "retrieval miss"
    if event.kind == EventKind.SUMMARY_GENERATED:
        return "generated summary"
    if event.kind == EventKind.COMPACTION_RUN:
        return "ran compaction"
    if event.kind == EventKind.SESSION_STARTED:
        return "session started"
    if event.kind == EventKind.SESSION_ENDED:
        return "session ended"
    return f"{event.kind.value} {target}"


def _flags_for_step(events: list[MemoryEvent], step: int) -> list[str]:
    flags: list[str] = []
    if find_first_duplicate_event(events) == step:
        flags.append("first_duplicate")
    if find_first_contradiction_event(events) == step:
        flags.append("first_contradiction")
    event = events[step - 1]
    if event.kind == EventKind.MEMORY_RETRIEVAL_MISS:
        flags.append("retrieval_miss")
    if event.kind == EventKind.MEMORY_RETRIEVED and event.metadata.get("stale") is True:
        flags.append("stale_recall")
    return flags


def build_timeline(events: list[MemoryEvent]) -> list[ReplayTimelineEntry]:
    timeline: list[ReplayTimelineEntry] = []
    session_id = events[0].session_id if events else ""
    for index, event in enumerate(events, start=1):
        snapshot = build_snapshot(session_id, events, index)
        timeline.append(
            ReplayTimelineEntry(
                step=index,
                timestamp=event.timestamp,
                kind=event.kind.value,
                memory_id=event.memory_id,
                query=event.query,
                summary=summarize_event(event),
                snapshot_memory_count=len(snapshot.memories),
                flags=_flags_for_step(events, index),
            )
        )
    return timeline


def replay_session(events: list[MemoryEvent]) -> ReplayResult:
    final_snapshot = build_snapshot(events[0].session_id, events) if events else build_snapshot("", [])
    return ReplayResult(
        session_id=events[0].session_id if events else "",
        total_steps=len(events),
        issue_first_seen={
            "duplicate": find_first_duplicate_event(events),
            "contradiction": find_first_contradiction_event(events),
        },
        timeline=build_timeline(events),
        final_snapshot_memory_count=len(final_snapshot.memories),
        final_memory_ids=sorted(final_snapshot.memories),
    )


def inspect_step(events: list[MemoryEvent], step: int) -> StepInspection:
    if not events:
        raise ValueError("No events available for replay.")
    if step < 1 or step > len(events):
        raise ValueError(f"Step {step} is out of range for {len(events)} events.")
    event = events[step - 1]
    previous_step = max(0, step - 1)
    previous_snapshot = build_snapshot(events[0].session_id, events, previous_step)
    current_snapshot = build_snapshot(events[0].session_id, events, step)
    return StepInspection(
        session_id=events[0].session_id,
        step=step,
        total_steps=len(events),
        summary=summarize_event(event),
        event=event.to_dict(),
        snapshot=current_snapshot.memories,
        delta_from_previous=diff_snapshots(previous_snapshot, current_snapshot),
        flags=_flags_for_step(events, step),
    )


def diff_steps(events: list[MemoryEvent], before_step: int, after_step: int) -> dict[str, object]:
    if not events:
        raise ValueError("No events available for replay.")
    before = build_snapshot(events[0].session_id, events, before_step)
    after = build_snapshot(events[0].session_id, events, after_step)
    diff = diff_snapshots(before, after)
    details: dict[str, dict[str, object | None]] = {}
    for memory_id in diff["created"]:
        details[memory_id] = {"before": None, "after": after.memories.get(memory_id)}
    for memory_id in diff["updated"]:
        details[memory_id] = {
            "before": before.memories.get(memory_id),
            "after": after.memories.get(memory_id),
        }
    for memory_id in diff["deleted"]:
        details[memory_id] = {"before": before.memories.get(memory_id), "after": None}
    return {
        "session_id": events[0].session_id,
        "before_step": before.step,
        "after_step": after.step,
        "before_count": len(before.memories),
        "after_count": len(after.memories),
        **diff,
        "details": details,
    }
