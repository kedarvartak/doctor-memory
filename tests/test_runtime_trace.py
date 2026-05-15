from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memfs_doctor.runtime.letta_runtime import (
    RecordedLine,
    default_runtime_trace_path,
    default_transcript_path,
    infer_runtime_events_from_turns,
    InteractiveRuntimeRecorder,
    parse_transcript_turns,
    write_raw_transcript,
    write_runtime_trace,
)


class RuntimeTraceTests(unittest.TestCase):
    def test_infers_retrieval_and_miss_from_transcript(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "> What is my favorite tea?"),
            RecordedLine("2026-05-15T10:00:00.100000+00:00", "* Thinking..."),
            RecordedLine("2026-05-15T10:00:00.250000+00:00", "• Masala chai."),
            RecordedLine("2026-05-15T10:00:01+00:00", "> What is my favorite dessert?"),
            RecordedLine("2026-05-15T10:00:01.200000+00:00", "• I don't know that one yet. Want to tell me?"),
        ]

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].kind.value, "memory_retrieved")
        self.assertEqual(events[1].kind.value, "memory_retrieval_miss")
        self.assertEqual(events[0].latency_ms, 250.0)
        self.assertEqual(events[1].latency_ms, 200.0)

    def test_runtime_trace_writer_outputs_jsonl(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "> What is my favorite tea?"),
            RecordedLine("2026-05-15T10:00:00.250000+00:00", "• Masala chai."),
        ]
        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = default_runtime_trace_path(Path(tmpdir), "session-001")
            written = write_runtime_trace(path, events)
            payloads = [json.loads(line) for line in written.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(len(payloads), 1)
            self.assertEqual(payloads[0]["kind"], "memory_retrieved")
            self.assertEqual(payloads[0]["session_id"], "session-001")

    def test_stdin_recording_emits_query_lines(self) -> None:
        recorder = InteractiveRuntimeRecorder()
        recorder._record_stdin_bytes(b"What is my favorite tea?")
        recorder._record_stdin_bytes(b"\n")
        recorder._record_stdin_bytes(b"What is my favorite dessert?")
        recorder._record_stdin_bytes(b"\n")

        turns = parse_transcript_turns(recorder.lines)
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[0].query, "What is my favorite tea?")
        self.assertEqual(turns[1].query, "What is my favorite dessert?")

    def test_raw_transcript_writer_outputs_lines(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "> What is my favorite tea?"),
            RecordedLine("2026-05-15T10:00:00.250000+00:00", "• Masala chai."),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            path = default_transcript_path(Path(tmpdir), "session-001")
            written = write_raw_transcript(path, lines)
            text = written.read_text(encoding="utf-8")
            self.assertIn("What is my favorite tea?", text)
            self.assertIn("Masala chai.", text)


if __name__ == "__main__":
    unittest.main()
