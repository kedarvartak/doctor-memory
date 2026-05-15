from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from memfs_doctor.adapters.letta import LettaTraceAdapter
from memfs_doctor.core.metrics import compute_metrics
from memfs_doctor.core.replay import diff_steps, inspect_step, replay_session
from memfs_doctor.storage.sqlite import SQLiteEventStore


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class WorkflowTests(unittest.TestCase):
    def test_ingest_metrics_and_replay(self) -> None:
        adapter = LettaTraceAdapter()
        events = adapter.load_events(FIXTURE)
        self.assertEqual(len(events), 9)

        metrics = compute_metrics(events)
        self.assertEqual(metrics.values["retrieval_count"], 2)
        self.assertGreater(metrics.values["duplicate_rate"], 0.0)
        self.assertGreater(metrics.values["contradiction_score"], 0.0)

        replay = replay_session(events)
        self.assertEqual(replay.issue_first_seen["duplicate"], 4)
        self.assertEqual(replay.issue_first_seen["contradiction"], 6)
        self.assertEqual(replay.final_snapshot_memory_count, 3)
        self.assertEqual(replay.timeline[3].flags, ["first_duplicate"])
        self.assertEqual(replay.timeline[5].flags, ["first_contradiction"])

        diff = diff_steps(events, 2, 6)
        self.assertIn("mem-003", diff["created"])
        self.assertIn("mem-001", diff["updated"])
        self.assertIn("details", diff)

        step = inspect_step(events, 5)
        self.assertEqual(step.step, 5)
        self.assertEqual(step.delta_from_previous["updated"], ["mem-001"])
        self.assertIn("mem-001", step.snapshot)
        self.assertEqual(step.summary, "updated mem-001")

    def test_sqlite_round_trip(self) -> None:
        adapter = LettaTraceAdapter()
        events = adapter.load_events(FIXTURE)

        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteEventStore(Path(tmpdir) / "events.db")
            store.init_db()
            ingested = store.ingest_events(events)
            self.assertEqual(ingested, len(events))

            sessions = store.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, "session-001")

            round_trip = store.get_session_events("session-001")
            self.assertEqual(len(round_trip), len(events))


if __name__ == "__main__":
    unittest.main()
