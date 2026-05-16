from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from memops.core.events import EventKind
from memops.runtime.letta_structured import emit_structured_retrieval, emit_structured_retrieval_miss
from memops.runtime.letta_runtime import (
    AGENT_ID_ENV,
    SESSION_ID_ENV,
    STRUCTURED_TRACE_PATH_ENV,
    RecordedLine,
    default_runtime_trace_path,
    default_structured_trace_path,
    default_transcript_path,
    drop_pre_resume_output,
    infer_runtime_events_from_turns,
    InteractiveRuntimeRecorder,
    load_structured_runtime_events,
    merge_runtime_events,
    normalize_response_lines,
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

        texts = [line.text for line in recorder.lines]
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0], "> What is my favorite tea?")
        self.assertEqual(texts[1], "> What is my favorite dessert?")

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

    def test_parses_real_letta_prompt_redraws(self) -> None:
        lines = [
            RecordedLine("2026-05-15T15:37:14.431155+00:00", "       › which phone do i have"),
            RecordedLine("2026-05-15T15:37:14.431191+00:00", "       ✻ Thinking…"),
            RecordedLine("2026-05-15T15:37:14.431255+00:00", "       • iPhone 15."),
            RecordedLine("2026-05-15T15:37:14.431364+00:00", "       › What is my favorite dessert?"),
            RecordedLine("2026-05-15T15:37:14.431401+00:00", "       ✻ Thinking…"),
            RecordedLine(
                "2026-05-15T15:37:14.431458+00:00",
                "       • Still don't know that one. You didn't tell me last time either — want to?",
            ),
            RecordedLine("2026-05-15T15:37:14.431491+00:00", "       › actually, my current phone is iphone 17"),
            RecordedLine(
                "2026-05-15T15:37:14.431524+00:00",
                '       • memory "Update phone from iPhone 15 to iPhone 17 per user\'s correction" in',
            ),
            RecordedLine("2026-05-15T15:37:14.431650+00:00", "       • Updated. iPhone 17."),
            RecordedLine("2026-05-15T15:37:14.431684+00:00", "       › what is my phone model rn"),
            RecordedLine("2026-05-15T15:37:14.431719+00:00", "       ✻ Thinking…"),
            RecordedLine("2026-05-15T15:37:14.431773+00:00", "       • iPhone 17."),
        ]

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].kind.value, "memory_retrieved")
        self.assertEqual(events[1].kind.value, "memory_retrieval_miss")
        self.assertEqual(events[2].kind.value, "memory_retrieved")

    def test_ignores_status_only_duplicate_before_real_answer(self) -> None:
        lines = [
            RecordedLine("2026-05-15T15:50:37.438511+00:00", "› what is my surname"),
            RecordedLine("2026-05-15T15:50:37.452399+00:00", "• Letta Code is remembering… (esc to interrupt)"),
            RecordedLine("2026-05-15T15:50:37.463792+00:00", "› what is my surname"),
            RecordedLine("2026-05-15T15:50:37.463891+00:00", "• Letta Code is remembering… (esc to interrupt)"),
            RecordedLine("2026-05-15T15:50:49.092979+00:00", "✻ Thinking…"),
            RecordedLine("2026-05-15T15:50:49.530604+00:00", "• Damian."),
        ]

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind.value, "memory_retrieved")
        self.assertEqual(events[0].query, "what is my surname")

    def test_normalizes_terminal_noise_from_response_lines(self) -> None:
        cleaned = normalize_response_lines(
            [
                "Honda.",
                "≡ Letta Code is formulating… (esc to interrupt)",
                "────────────────────────────────────────────",
                "›",
                "→ /agents    list all agents",
                "Session usage: 13 steps",
                "Resume this agent with:",
            ]
        )

        self.assertEqual(cleaned, ["Honda."])

    def test_inferred_runtime_recall_keeps_clean_response_text_only(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "> what car do i have"),
            RecordedLine("2026-05-15T10:00:00.100000+00:00", "• Honda."),
            RecordedLine("2026-05-15T10:00:00.110000+00:00", "• Letta Code is formulating… (esc to interrupt)"),
            RecordedLine("2026-05-15T10:00:00.120000+00:00", "────────────────────────────────────────────"),
            RecordedLine("2026-05-15T10:00:00.130000+00:00", "›"),
            RecordedLine("2026-05-15T10:00:00.140000+00:00", "Resume this agent with:"),
        ]

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["response_text"], "Honda.")

    def test_truncates_response_after_first_real_answer_before_footer_noise(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "> do u remember im an alias"),
            RecordedLine("2026-05-15T10:00:16+00:00", "• Yeah — Tomato. It's in my memory."),
            RecordedLine("2026-05-15T10:00:16.100000+00:00", "• Letta Code is indexing… (esc to interrupt)"),
            RecordedLine("2026-05-15T10:00:16.200000+00:00", "└ Tip: Use /remember [instructions] to remember something from the conversation."),
            RecordedLine("2026-05-15T10:00:16.300000+00:00", "────────────────────────────────────────────────────────"),
            RecordedLine("2026-05-15T10:00:16.400000+00:00", "Resume this conversation with:"),
            RecordedLine("2026-05-15T10:00:16.500000+00:00", "letta --conv conv-123"),
        ]

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].metadata["response_text"], "Yeah — Tomato. It's in my memory.")

    def test_drops_pre_resume_output_before_parsing_turns(self) -> None:
        lines = [
            RecordedLine("2026-05-15T10:00:00+00:00", "• Honda."),
            RecordedLine("2026-05-15T10:00:00.050000+00:00", "• Resuming conversation with Letta Code"),
            RecordedLine("2026-05-15T10:00:01+00:00", "> my height is ?"),
            RecordedLine("2026-05-15T10:00:01.020000+00:00", "• Still don't know that one."),
        ]

        filtered = drop_pre_resume_output(lines)
        self.assertEqual(len(filtered), 2)
        self.assertEqual(filtered[0].text, "> my height is ?")

        turns = parse_transcript_turns(lines)
        events = infer_runtime_events_from_turns(
            turns,
            agent_id="agent-001",
            session_id="session-001",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind.value, "memory_retrieval_miss")
        self.assertEqual(events[0].query, "my height is ?")

    def test_loads_structured_runtime_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = default_structured_trace_path(Path(tmpdir), "session-001")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "kind": "memory_retrieved",
                        "query": "what car do i have",
                        "memory_id": "system/human.md",
                        "related_memory_ids": ["mem-2"],
                        "latency_ms": 42.0,
                        "tokens_loaded": 12,
                        "score": 0.93,
                        "metadata": {"used": True, "stale": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            events = load_structured_runtime_events(path, agent_id="agent-001", session_id="session-001")

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].kind.value, "memory_retrieved")
            self.assertEqual(events[0].memory_id, "system/human.md")
            self.assertEqual(events[0].tokens_loaded, 12)

    def test_structured_runtime_events_override_heuristic_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            heuristic = [
                infer_runtime_events_from_turns(
                    parse_transcript_turns(
                        [
                            RecordedLine("2026-05-15T10:00:00+00:00", "> what car do i have"),
                            RecordedLine("2026-05-15T10:00:00.250000+00:00", "• Honda."),
                        ]
                    ),
                    agent_id="agent-001",
                    session_id="session-001",
                )[0]
            ]
            path = Path(tmpdir) / "structured.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "kind": "memory_retrieved",
                        "query": "what car do i have",
                        "memory_id": "system/human.md",
                        "latency_ms": 21.0,
                        "tokens_loaded": 18,
                        "score": 0.97,
                        "metadata": {"used": True, "structured": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            structured = load_structured_runtime_events(path, agent_id="agent-001", session_id="session-001")

            merged = merge_runtime_events(heuristic, structured)

            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0].memory_id, "system/human.md")
            self.assertEqual(merged[0].tokens_loaded, 18)

    def test_emits_structured_retrieval_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "structured.jsonl"
            old_env = {
                STRUCTURED_TRACE_PATH_ENV: os.environ.get(STRUCTURED_TRACE_PATH_ENV),
                AGENT_ID_ENV: os.environ.get(AGENT_ID_ENV),
                SESSION_ID_ENV: os.environ.get(SESSION_ID_ENV),
            }
            os.environ[STRUCTURED_TRACE_PATH_ENV] = str(path)
            os.environ[AGENT_ID_ENV] = "agent-001"
            os.environ[SESSION_ID_ENV] = "session-001"
            try:
                emit_structured_retrieval(query="what car do i have", memory_id="system/human.md", score=0.91)
                emit_structured_retrieval_miss(query="what is my height", reason="no_relevant_memory")
            finally:
                for key, value in old_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

            payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(payloads), 2)
            self.assertEqual(payloads[0]["kind"], EventKind.MEMORY_RETRIEVED.value)
            self.assertEqual(payloads[1]["kind"], EventKind.MEMORY_RETRIEVAL_MISS.value)


if __name__ == "__main__":
    unittest.main()
