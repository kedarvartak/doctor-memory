from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from memfs_doctor.adapters.letta.adapter import LettaLocalState, LettaTraceAdapter
from memfs_doctor.core.metrics import compute_metrics


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

            adapter = LettaTraceAdapter(state=LettaLocalState(home))
            agents = adapter.discover_agents()

            self.assertEqual(len(agents), 1)
            self.assertEqual(agents[0].agent_id, "agent-001")
            self.assertEqual(agents[0].memory_dir, memory_dir)

    def test_imports_git_history_as_memory_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_dir = Path(tmpdir) / "memory"
            self._create_memfs_repo(memory_dir)

            adapter = LettaTraceAdapter(state=LettaLocalState(Path(tmpdir)))
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
