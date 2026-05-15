from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memfs_doctor.adapters.letta import LettaLocalState, LettaTraceAdapter
from memfs_doctor.storage.sqlite import SQLiteEventStore


class CliDefaultsTests(unittest.TestCase):
    def test_letta_state_resolves_default_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            root = home / ".letta"
            root.mkdir(parents=True)
            (root / "settings.json").write_text(
                json.dumps(
                    {
                        "lastAgent": "agent-123",
                        "lastSession": {"agentId": "agent-123", "conversationId": "default"},
                    }
                ),
                encoding="utf-8",
            )
            state = LettaLocalState(home=home, workspace_root=home)
            self.assertEqual(state.get_default_agent_id(), "agent-123")

    def test_letta_adapter_uses_latest_capture_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            adapter = LettaTraceAdapter(state=LettaLocalState(home=home, workspace_root=home))
            memory_dir = home / ".letta" / "agents" / "agent-123" / "memory"
            (memory_dir / ".letta").mkdir(parents=True)
            (memory_dir / ".letta" / "config.json").write_text('{"version":1}\n', encoding="utf-8")
            (memory_dir / "system").mkdir()
            (memory_dir / "system" / "persona.md").write_text("---\ndescription: Persona\n---\nBase\n", encoding="utf-8")
            (memory_dir / "system" / "human.md").write_text("---\ndescription: Human\n---\nBase\n", encoding="utf-8")

            capture_one = adapter.state.save_capture_for_test(
                capture_id="letta-session:agent-123:default:one",
                agent_id="agent-123",
                memory_dir=memory_dir,
                base_head="abc",
                started_at="2026-05-15T10:00:00+00:00",
                conversation_id="default",
            )
            capture_two = adapter.state.save_capture_for_test(
                capture_id="letta-session:agent-123:default:two",
                agent_id="agent-123",
                memory_dir=memory_dir,
                base_head="def",
                started_at="2026-05-15T10:05:00+00:00",
                conversation_id="default",
            )

            latest = adapter.state.latest_capture()
            self.assertEqual(latest.capture_id, capture_two.capture_id)
            self.assertNotEqual(latest.capture_id, capture_one.capture_id)

    def test_event_store_returns_latest_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db = SQLiteEventStore(Path(tmpdir) / "events.db")
            db.init_db()

            adapter = LettaTraceAdapter(state=LettaLocalState(home=Path(tmpdir), workspace_root=Path(tmpdir)))
            first = adapter.load_events(Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl")
            db.ingest_events(first)

            second = [event for event in first]
            for index, event in enumerate(second, start=1):
                event.session_id = "session-002"
                event.event_id = f"session-002:{index}"
                event.timestamp = "2026-05-16T10:00:00+00:00"
            db.ingest_events(second)

            latest_one = db.latest_session_ids(1)
            latest_two = db.latest_session_ids(2)

            self.assertEqual(latest_one, ["session-002"])
            self.assertEqual(latest_two, ["session-002", "session-001"])


if __name__ == "__main__":
    unittest.main()

