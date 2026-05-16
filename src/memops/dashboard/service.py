from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from memops.core.metrics import compute_metrics
from memops.core.replay import replay_session
from memops.core.reporting import HealthReport, evaluate_thresholds, load_threshold_rules
from memops.core.retrievals import analyze_retrievals, top_problematic_recalls
from memops.storage.sqlite import SQLiteEventStore


@dataclass(slots=True)
class DashboardSessionSummary:
    session_id: str
    framework: str
    agent_id: str
    started_at: str | None
    ended_at: str | None
    event_count: int
    live_status: str | None = None
    last_turn_index: int | None = None
    last_query: str | None = None
    last_updated_at: str | None = None
    has_ingested_events: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DashboardService:
    def __init__(self, store: SQLiteEventStore) -> None:
        self.store = store
        self.store.init_db()

    def overview(self, limit: int = 20) -> dict[str, Any]:
        return {
            "db_path": str(self.store.db_path),
            "event_count": self.store.total_event_count(),
            "health_snapshot_count": self.store.total_health_snapshot_count(),
            "sessions": [item.to_dict() for item in self.list_sessions(limit=limit)],
        }

    def list_sessions(self, limit: int = 20) -> list[DashboardSessionSummary]:
        event_sessions = {item.session_id: item for item in self.store.list_sessions()}
        snapshot_sessions = self.store.list_snapshot_sessions(limit=max(limit, 50))

        merged: dict[str, DashboardSessionSummary] = {}
        for session in event_sessions.values():
            merged[session.session_id] = DashboardSessionSummary(
                session_id=session.session_id,
                framework=session.framework,
                agent_id=session.agent_id,
                started_at=session.started_at,
                ended_at=session.ended_at,
                event_count=session.event_count,
                has_ingested_events=True,
            )

        for snapshot in snapshot_sessions:
            item = merged.get(snapshot["session_id"])
            if item is None:
                merged[snapshot["session_id"]] = DashboardSessionSummary(
                    session_id=snapshot["session_id"],
                    framework=snapshot["framework"],
                    agent_id=snapshot["agent_id"],
                    started_at=None,
                    ended_at=None,
                    event_count=0,
                    live_status=snapshot["status"],
                    last_turn_index=snapshot["turn_index"],
                    last_query=snapshot["query"],
                    last_updated_at=snapshot["updated_at"],
                    has_ingested_events=False,
                )
                continue
            item.live_status = snapshot["status"]
            item.last_turn_index = snapshot["turn_index"]
            item.last_query = snapshot["query"]
            item.last_updated_at = snapshot["updated_at"]

        ordered = sorted(
            merged.values(),
            key=lambda item: item.last_updated_at or item.started_at or "",
            reverse=True,
        )
        return ordered[:limit]

    def session_detail(self, session_id: str) -> dict[str, Any]:
        snapshots = self.store.list_health_snapshots(session_id)
        events = self.store.get_session_events(session_id)
        replay = replay_session(events).to_dict() if events else None
        retrievals = analyze_retrievals(events).to_dict() if events else None
        report = self._health_report(events).to_dict() if events else None
        return {
            "session_id": session_id,
            "snapshots": snapshots,
            "report": report,
            "replay": replay,
            "retrievals": retrievals,
        }

    def _health_report(self, events) -> HealthReport:
        metrics = compute_metrics(events)
        findings = evaluate_thresholds(metrics, load_threshold_rules())
        retrievals = analyze_retrievals(events)
        return HealthReport.from_metrics(metrics, findings, top_problematic_recalls(retrievals.traces))
