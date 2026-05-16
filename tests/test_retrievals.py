from __future__ import annotations

import unittest
from pathlib import Path

from memops.adapters.letta import LettaTraceAdapter
from memops.core.events import EventKind, MemoryEvent
from memops.core.retrievals import analyze_retrievals, retrieval_trace_for_step, top_problematic_recalls


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class RetrievalTraceTests(unittest.TestCase):
    def test_analyzes_retrieval_causality_and_quality(self) -> None:
        adapter = LettaTraceAdapter()
        events = adapter.load_events(FIXTURE)

        report = analyze_retrievals(events)

        self.assertEqual(report.retrieval_count, 2)
        self.assertEqual(report.miss_count, 1)

        first = retrieval_trace_for_step(events, 3)
        self.assertEqual(first.memory_id, "mem-001")
        self.assertEqual(first.cause_step, 2)
        self.assertEqual(first.cause_kind, "memory_created")
        self.assertTrue(first.likely_useful)
        self.assertFalse(first.likely_noisy)

        second = retrieval_trace_for_step(events, 8)
        self.assertEqual(second.memory_id, "mem-001")
        self.assertEqual(second.cause_step, 5)
        self.assertTrue(second.stale)
        self.assertTrue(second.likely_noisy)

    def test_surfaces_top_problematic_recalls(self) -> None:
        adapter = LettaTraceAdapter()
        events = adapter.load_events(FIXTURE)

        report = analyze_retrievals(events)
        problematic = top_problematic_recalls(report.traces)

        self.assertEqual(len(problematic), 1)
        self.assertEqual(problematic[0].step, 8)
        self.assertIn("Priya", problematic[0].cause_summary or "")

    def test_inferred_runtime_recall_is_not_marked_useful_without_evidence(self) -> None:
        events = [
            MemoryEvent(
                event_id="s:start",
                kind=EventKind.SESSION_STARTED,
                framework="letta",
                agent_id="agent-001",
                session_id="session-001",
                timestamp="2026-05-15T10:00:00+00:00",
                source="runtime",
            ),
            MemoryEvent(
                event_id="s:1",
                kind=EventKind.MEMORY_RETRIEVED,
                framework="letta",
                agent_id="agent-001",
                session_id="session-001",
                timestamp="2026-05-15T10:00:01+00:00",
                source="runtime",
                query="what bike do i have",
                metadata={"inferred": True, "response_text": "Pulsar N150."},
                latency_ms=2000.0,
            ),
        ]

        report = analyze_retrievals(events)
        trace = report.traces[0]

        self.assertFalse(trace.likely_useful)
        self.assertFalse(trace.likely_noisy)

    def test_inferred_runtime_recall_with_noisy_response_is_problematic(self) -> None:
        events = [
            MemoryEvent(
                event_id="s:start",
                kind=EventKind.SESSION_STARTED,
                framework="letta",
                agent_id="agent-001",
                session_id="session-001",
                timestamp="2026-05-15T10:00:00+00:00",
                source="runtime",
            ),
            MemoryEvent(
                event_id="s:1",
                kind=EventKind.MEMORY_RETRIEVED,
                framework="letta",
                agent_id="agent-001",
                session_id="session-001",
                timestamp="2026-05-15T10:00:01+00:00",
                source="runtime",
                query="what car do i have",
                metadata={
                    "inferred": True,
                    "response_text": "Honda. Session usage: 13 steps Resume this agent with: letta -n",
                },
                latency_ms=5000.0,
            ),
        ]

        report = analyze_retrievals(events)
        trace = report.traces[0]

        self.assertTrue(trace.likely_noisy)


if __name__ == "__main__":
    unittest.main()
