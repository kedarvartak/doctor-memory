from __future__ import annotations

from datetime import datetime, timedelta
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from memops.adapters.letta.adapter import LettaLocalState, LettaTraceAdapter
from memops.core.metrics import compute_metrics
from memops.storage.sqlite import SQLiteEventStore


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


class LettaAdapterTests(unittest.TestCase):
    def test_discovers_local_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            memory_dir = home / ".letta" / "agents" / "agent-001" / "memory"
            (memory_dir / ".letta").mkdir(parents=True)
            (memory_dir / ".letta" / "config.json").write_text('{"version": 1}\n', encoding="utf-8")
            (memory_dir / "system").mkdir()
            (memory_dir / "system" / "persona.md").write_text("---\ndescription: Persona\n---\nHello\n", encoding="utf-8")
            (memory_dir / "system" / "human.md").write_text("---\ndescription: Human\n---\nHi\n", encoding="utf-8")

            adapter = LettaTraceAdapter(state=LettaLocalState(home=home, workspace_root=home))
            agents = adapter.discover_agents()

            self.assertEqual(len(agents), 1)
            self.assertEqual(agents[0].agent_id, "agent-001")
            self.assertEqual(agents[0].memory_dir, memory_dir)

    def test_imports_git_history_as_memory_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            self._create_memfs_repo(memory_dir)

            adapter = LettaTraceAdapter(state=LettaLocalState(home=Path(tmpdir), workspace_root=Path(tmpdir)))
            events = adapter.load_events_from_memory_repo(memory_dir)

            kinds = [event.kind.value for event in events]
            self.assertIn("session_started", kinds)
            self.assertIn("memory_created", kinds)
            self.assertIn("memory_updated", kinds)
            self.assertIn("memory_deleted", kinds)
            self.assertIn("session_ended", kinds)

            memory_events = [event for event in events if event.memory_id == "facts/user.md"]
            self.assertTrue(memory_events)
            self.assertEqual(memory_events[0].after["content"], "User likes tea.")
            self.assertIn("green tea", memory_events[1].after["content"])

            metrics = compute_metrics(events)
            self.assertEqual(metrics.values["contradiction_score"], 0.0)

    def test_captures_incremental_session_window_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            memory_dir = home / ".letta" / "agents" / "agent-001" / "memory"
            self._create_memfs_repo(memory_dir)

            adapter = LettaTraceAdapter(state=LettaLocalState(home=home, workspace_root=home))
            capture = adapter.start_session_capture(agent_id="agent-001")

            file_path = memory_dir / "facts" / "user.md"
            file_path.write_text("---\ndescription: User fact\n---\nUser likes jasmine tea.\n", encoding="utf-8")
            run_git(memory_dir, "add", ".")
            run_git(memory_dir, "commit", "-m", "Session update")

            other_path = memory_dir / "facts" / "food.md"
            other_path.write_text("---\ndescription: Food fact\n---\nUser likes dosa.\n", encoding="utf-8")
            run_git(memory_dir, "add", ".")
            run_git(memory_dir, "commit", "-m", "Session add food fact")

            events = adapter.finish_session_capture(capture.capture_id)
            mutation_events = [event for event in events if event.kind.value.startswith("memory_")]

            self.assertEqual(len(mutation_events), 2)
            self.assertTrue(all(event.session_id == capture.capture_id for event in events))
            self.assertEqual(mutation_events[0].memory_id, "facts/user.md")
            self.assertEqual(mutation_events[1].memory_id, "facts/food.md")

            store = SQLiteEventStore(home / "events.db")
            store.init_db()
            store.ingest_events(events)
            sessions = store.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0].session_id, capture.capture_id)

    def test_finish_capture_merges_runtime_trace_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            memory_dir = home / ".letta" / "agents" / "agent-001" / "memory"
            self._create_memfs_repo(memory_dir)

            adapter = LettaTraceAdapter(state=LettaLocalState(home=home, workspace_root=home))
            capture = adapter.start_session_capture(agent_id="agent-001")
            ts_one = capture.started_at
            ts_two = capture.started_at

            runtime_trace = home / "runtime.jsonl"
            runtime_trace.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "event_id": "rt-1",
                                "kind": "memory_retrieved",
                                "framework": "letta",
                                "agent_id": "agent-001",
                                "session_id": "ignored-session",
                                "timestamp": ts_one,
                                "source": "letta-runtime",
                                "memory_id": "facts/user.md",
                                "query": "What does the user like?",
                                "metadata": {"used": True, "stale": False},
                                "latency_ms": 21.5,
                                "tokens_loaded": 18,
                                "score": 0.92,
                            }
                        ),
                        json.dumps(
                            {
                                "event_id": "rt-2",
                                "kind": "memory_retrieval_miss",
                                "framework": "letta",
                                "agent_id": "agent-001",
                                "session_id": "ignored-session",
                                "timestamp": ts_two,
                                "source": "letta-runtime",
                                "query": "What is the user's favorite dessert?",
                                "metadata": {"reason": "no_relevant_memory"},
                                "latency_ms": 19.0,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            events = adapter.finish_session_capture(capture.capture_id, runtime_trace_path=runtime_trace)
            retrievals = [event for event in events if event.kind.value == "memory_retrieved"]
            misses = [event for event in events if event.kind.value == "memory_retrieval_miss"]

            self.assertEqual(len(retrievals), 1)
            self.assertEqual(len(misses), 1)
            self.assertEqual(retrievals[0].session_id, capture.capture_id)
            self.assertEqual(retrievals[0].latency_ms, 21.5)
            self.assertEqual(retrievals[0].tokens_loaded, 18)
            self.assertEqual(misses[0].metadata["reason"], "no_relevant_memory")

    def _create_memfs_repo(self, memory_dir: Path) -> None:
        (memory_dir / ".letta").mkdir(parents=True)
        (memory_dir / "system").mkdir()
        (memory_dir / "facts").mkdir()

        (memory_dir / ".letta" / "config.json").write_text(json.dumps({"version": 1}) + "\n", encoding="utf-8")
        (memory_dir / "system" / "persona.md").write_text("---\ndescription: Persona\n---\nBase persona\n", encoding="utf-8")
        (memory_dir / "system" / "human.md").write_text("---\ndescription: Human\n---\nBase human\n", encoding="utf-8")

        subprocess.run(["git", "init", str(memory_dir)], check=True, capture_output=True, text=True)
        run_git(memory_dir, "config", "user.email", "tester@example.com")
        run_git(memory_dir, "config", "user.name", "Tester")

        file_path = memory_dir / "facts" / "user.md"
        file_path.write_text("---\ndescription: User fact\n---\nUser likes tea.\n", encoding="utf-8")
        run_git(memory_dir, "add", ".")
        run_git(memory_dir, "commit", "-m", "Add user fact")

        file_path.write_text("---\ndescription: User fact\n---\nUser likes green tea.\n", encoding="utf-8")
        run_git(memory_dir, "add", ".")
        run_git(memory_dir, "commit", "-m", "Update user fact")

        file_path.unlink()
        run_git(memory_dir, "add", "-A")
        run_git(memory_dir, "commit", "-m", "Remove user fact")


if __name__ == "__main__":
    unittest.main()
