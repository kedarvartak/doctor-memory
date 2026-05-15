from __future__ import annotations

import unittest
from pathlib import Path

from memfs_doctor.adapters.letta import LettaTraceAdapter
from memfs_doctor.core.retrievals import analyze_retrievals, retrieval_trace_for_step, top_problematic_recalls


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


if __name__ == "__main__":
    unittest.main()
