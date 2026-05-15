from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from memfs_doctor.core.metrics import compute_metrics
from memfs_doctor.core.reporting import (
    ComparisonReport,
    HealthReport,
    compare_reports,
    default_thresholds,
    evaluate_thresholds,
    export_report,
)
from memfs_doctor.adapters.letta import LettaLocalState, LettaTraceAdapter


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class ReportingTests(unittest.TestCase):
    def test_health_report_thresholds_and_export(self) -> None:
        adapter = LettaTraceAdapter(state=LettaLocalState(home=Path("/tmp"), workspace_root=Path("/tmp")))
        events = adapter.load_events(FIXTURE)
        metrics = compute_metrics(events)
        thresholds = default_thresholds()
        findings = evaluate_thresholds(metrics, thresholds)

        report = HealthReport.from_metrics(metrics=metrics, findings=findings)
        self.assertEqual(report.status, "error")
        self.assertTrue(any(item.metric == "duplicate_rate" for item in report.findings))

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_report(Path(tmpdir) / "report.json", report.to_dict())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["session_id"], "session-001")
            self.assertIn("metrics", payload)
            self.assertIn("findings", payload)

    def test_compare_reports_flags_regressions(self) -> None:
        baseline = HealthReport(
            session_id="baseline",
            framework="letta",
            agent_id="agent-1",
            status="healthy",
            metrics={
                "retrieval_latency_ms_avg": 100.0,
                "empty_retrieval_rate": 0.1,
                "duplicate_rate": 0.0,
            },
            findings=[],
        )
        candidate = HealthReport(
            session_id="candidate",
            framework="letta",
            agent_id="agent-1",
            status="warning",
            metrics={
                "retrieval_latency_ms_avg": 180.0,
                "empty_retrieval_rate": 0.3,
                "duplicate_rate": 0.25,
            },
            findings=[],
        )

        comparison = compare_reports(baseline, candidate)
        self.assertIsInstance(comparison, ComparisonReport)
        self.assertEqual(comparison.regression_count, 3)
        self.assertTrue(any(item["metric"] == "duplicate_rate" for item in comparison.regressions))
        self.assertAlmostEqual(comparison.deltas["retrieval_latency_ms_avg"]["delta"], 80.0)


if __name__ == "__main__":
    unittest.main()
