from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memops.adapters.letta import LettaTraceAdapter
from memops.dashboard.service import DashboardService
from memops.storage.sqlite import SQLiteEventStore


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class DashboardTests(unittest.TestCase):
    def test_health_snapshot_storage_and_session_listing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteEventStore(Path(tmpdir) / "events.db")
            store.init_db()
            store.upsert_health_snapshot(
                capture_id="capture-001",
                session_id="capture-001",
                framework="letta",
                agent_id="agent-001",
                turn_index=1,
                query="what tea do i like",
                status="healthy",
                updated_at="2026-05-16T10:00:00+00:00",
                metrics={"memory_churn_rate": 0.0, "retrieval_latency_ms_avg": 120.0},
                findings=[],
            )
            store.upsert_health_snapshot(
                capture_id="capture-001",
                session_id="capture-001",
                framework="letta",
                agent_id="agent-001",
                turn_index=2,
                query="what tea do i like now",
                status="warning",
                updated_at="2026-05-16T10:01:00+00:00",
                metrics={"memory_churn_rate": 0.5, "retrieval_latency_ms_avg": 980.0},
                findings=[{"metric": "retrieval_latency_ms_avg", "severity": "warning"}],
            )

            snapshots = store.list_health_snapshots("capture-001")
            self.assertEqual(len(snapshots), 2)
            self.assertEqual(snapshots[-1]["status"], "warning")

            sessions = store.list_snapshot_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["turn_index"], 2)

    def test_dashboard_service_combines_live_snapshots_and_ingested_sessions(self) -> None:
        adapter = LettaTraceAdapter()
        events = adapter.load_events(FIXTURE)

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteEventStore(Path(tmpdir) / "events.db")
            store.init_db()
            store.ingest_events(events)
            store.upsert_health_snapshot(
                capture_id="session-001",
                session_id="session-001",
                framework="letta",
                agent_id="agent-123",
                turn_index=3,
                query="what tea do i like",
                status="healthy",
                updated_at="2026-05-16T10:02:00+00:00",
                metrics={"memory_churn_rate": 0.2, "retrieval_latency_ms_avg": 90.0},
                findings=[],
            )

            service = DashboardService(store)
            overview = service.overview()
            self.assertEqual(len(overview["sessions"]), 1)
            self.assertEqual(overview["sessions"][0]["session_id"], "session-001")
            self.assertEqual(overview["sessions"][0]["live_status"], "healthy")

            detail = service.session_detail("session-001")
            self.assertIn("report", detail)
            self.assertIn("replay", detail)
            self.assertEqual(len(detail["snapshots"]), 1)
            self.assertEqual(detail["replay"]["total_steps"], 9)


if __name__ == "__main__":
    unittest.main()

