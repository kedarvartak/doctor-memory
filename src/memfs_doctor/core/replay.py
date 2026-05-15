from __future__ import annotations

from dataclasses import dataclass

from memfs_doctor.core.events import EventKind, MemoryEvent
from memfs_doctor.core.snapshots import build_snapshot, diff_snapshots


@dataclass(slots=True)
class ReplayResult:
    session_id: str
    total_steps: int
    issue_first_seen: dict[str, int | None]
    timeline: list[str]


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


def build_timeline(events: list[MemoryEvent]) -> list[str]:
    lines: list[str] = []
    for index, event in enumerate(events, start=1):
        target = event.memory_id or "-"
        line = f"{index:03d} {event.timestamp} {event.kind.value} memory={target}"
        if event.query:
            line += f" query={event.query!r}"
        lines.append(line)
    return lines


def replay_session(events: list[MemoryEvent]) -> ReplayResult:
    return ReplayResult(
        session_id=events[0].session_id if events else "",
        total_steps=len(events),
        issue_first_seen={
            "duplicate": find_first_duplicate_event(events),
            "contradiction": find_first_contradiction_event(events),
        },
        timeline=build_timeline(events),
    )


def diff_steps(events: list[MemoryEvent], before_step: int, after_step: int) -> dict[str, list[str]]:
    before = build_snapshot(events[0].session_id, events, before_step)
    after = build_snapshot(events[0].session_id, events, after_step)
    return diff_snapshots(before, after)

