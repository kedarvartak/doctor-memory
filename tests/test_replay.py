from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memops.adapters.letta import LettaTraceAdapter
from memops.core.replay import inspect_step, replay_session
from memops.reports.render import render_step_inspection
from memops.storage.sqlite import SQLiteEventStore


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class ReplayTests(unittest.TestCase):
    def test_replay_to_dict_and_step_json(self) -> None:
        events = LettaTraceAdapter().load_events(FIXTURE)

        replay = replay_session(events)
        payload = replay.to_dict()
        self.assertEqual(payload["session_id"], "session-001")
        self.assertEqual(payload["timeline"][0]["step"], 1)
        self.assertEqual(payload["timeline"][-1]["step"], len(events))

        step = inspect_step(events, 3)
        rendered = render_step_inspection(step, as_json=True)
        parsed = json.loads(rendered)
        self.assertEqual(parsed["step"], 3)
        self.assertEqual(parsed["event"]["kind"], "memory_retrieved")

    def test_offline_trace_loading_matches_ingested_session(self) -> None:
        events = LettaTraceAdapter().load_events(FIXTURE)
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLiteEventStore(Path(tmpdir) / "events.db")
            store.init_db()
            store.ingest_events(events)

            from_store = store.get_session_events("session-001")
            self.assertEqual(replay_session(events).to_dict(), replay_session(from_store).to_dict())


if __name__ == "__main__":
    unittest.main()
