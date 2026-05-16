from __future__ import annotations

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

from memops.cli.main import main as cli_main
from memops.core.metrics import compute_metrics
from memops.core.reporting import (
    CheckResult,
    ComparisonReport,
    HealthReport,
    check_health_report,
    check_regression_report,
    compare_reports,
    default_regression_thresholds,
    default_thresholds,
    evaluate_regressions,
    evaluate_thresholds,
    export_report,
    load_regression_rules,
    load_threshold_rules,
)
from memops.core.retrievals import analyze_retrievals, top_problematic_recalls
from memops.adapters.letta import LettaLocalState, LettaTraceAdapter


FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "letta_session.jsonl"


class ReportingTests(unittest.TestCase):
    def test_health_report_thresholds_and_export(self) -> None:
        adapter = LettaTraceAdapter(state=LettaLocalState(home=Path("/tmp"), workspace_root=Path("/tmp")))
        events = adapter.load_events(FIXTURE)
        metrics = compute_metrics(events)
        thresholds = default_thresholds()
        findings = evaluate_thresholds(metrics, thresholds)
        retrievals = analyze_retrievals(events)

        report = HealthReport.from_metrics(
            metrics=metrics,
            findings=findings,
            problematic_recalls=top_problematic_recalls(retrievals.traces),
        )
        self.assertEqual(report.status, "error")
        self.assertTrue(any(item.metric == "duplicate_rate" for item in report.findings))
        self.assertEqual(len(report.problematic_recalls), 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_report(Path(tmpdir) / "report.json", report.to_dict())
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["session_id"], "session-001")
            self.assertIn("metrics", payload)
            self.assertIn("findings", payload)
            self.assertIn("problematic_recalls", payload)

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

        regression_findings = evaluate_regressions(comparison, default_regression_thresholds())
        self.assertTrue(any(item.metric == "duplicate_rate" for item in regression_findings))

        result = check_regression_report(comparison, regression_findings)
        self.assertIsInstance(result, CheckResult)
        self.assertEqual(result.status, "fail")
        self.assertEqual(result.exit_code, 1)

    def test_check_health_report_and_config_loading(self) -> None:
        adapter = LettaTraceAdapter(state=LettaLocalState(home=Path("/tmp"), workspace_root=Path("/tmp")))
        events = adapter.load_events(FIXTURE)
        metrics = compute_metrics(events)

        with tempfile.TemporaryDirectory() as tmpdir:
            threshold_path = Path(tmpdir) / "thresholds.json"
            threshold_path.write_text(
                json.dumps(
                    {
                        "thresholds": [
                            {"metric": "duplicate_rate", "operator": ">=", "warning": 0.05, "error": 0.2}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rules = load_threshold_rules(threshold_path)
            findings = evaluate_thresholds(metrics, rules)
            report = HealthReport.from_metrics(metrics, findings)
            result = check_health_report(report, fail_on="warning")
            self.assertEqual(result.status, "fail")
            self.assertEqual(result.exit_code, 1)

            regression_path = Path(tmpdir) / "regressions.json"
            regression_path.write_text(
                json.dumps(
                    {
                        "regressions": [
                            {"metric": "duplicate_rate", "operator": ">=", "warning_delta": 0.1, "error_delta": 0.2}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            rules = load_regression_rules(regression_path)
            self.assertEqual(rules[0].metric, "duplicate_rate")

    def test_benchmark_command_compares_two_trace_files(self) -> None:
        baseline_trace = "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "b-1",
                        "kind": "session_started",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "baseline-session",
                        "timestamp": "2026-05-16T10:00:00+00:00",
                        "source": "test",
                    }
                ),
                json.dumps(
                    {
                        "event_id": "b-2",
                        "kind": "memory_retrieved",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "baseline-session",
                        "timestamp": "2026-05-16T10:00:01+00:00",
                        "source": "test",
                        "memory_id": "mem-1",
                        "query": "what is my city",
                        "latency_ms": 50.0,
                        "tokens_loaded": 8,
                        "metadata": {"used": True, "stale": False},
                    }
                ),
                json.dumps(
                    {
                        "event_id": "b-3",
                        "kind": "session_ended",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "baseline-session",
                        "timestamp": "2026-05-16T10:00:02+00:00",
                        "source": "test",
                    }
                ),
            ]
        )
        candidate_trace = "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "c-1",
                        "kind": "session_started",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "candidate-session",
                        "timestamp": "2026-05-16T10:00:00+00:00",
                        "source": "test",
                    }
                ),
                json.dumps(
                    {
                        "event_id": "c-2",
                        "kind": "memory_updated",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "candidate-session",
                        "timestamp": "2026-05-16T10:00:01+00:00",
                        "source": "test",
                        "memory_id": "mem-1",
                        "before": {"content": "City is Pune", "attributes": {"city": "Pune"}},
                        "after": {"content": "City is Pune", "attributes": {"city": "Pune"}},
                    }
                ),
                json.dumps(
                    {
                        "event_id": "c-3",
                        "kind": "memory_retrieved",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "candidate-session",
                        "timestamp": "2026-05-16T10:00:02+00:00",
                        "source": "test",
                        "memory_id": "mem-1",
                        "query": "what is my city",
                        "latency_ms": 1600.0,
                        "tokens_loaded": 8,
                        "metadata": {"used": True, "stale": False},
                    }
                ),
                json.dumps(
                    {
                        "event_id": "c-4",
                        "kind": "session_ended",
                        "framework": "letta",
                        "agent_id": "agent-1",
                        "session_id": "candidate-session",
                        "timestamp": "2026-05-16T10:00:03+00:00",
                        "source": "test",
                    }
                ),
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_path = Path(tmpdir) / "baseline.jsonl"
            candidate_path = Path(tmpdir) / "candidate.jsonl"
            baseline_path.write_text(baseline_trace + "\n", encoding="utf-8")
            candidate_path.write_text(candidate_trace + "\n", encoding="utf-8")

            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = cli_main(
                    [
                        "benchmark",
                        "--baseline-trace",
                        str(baseline_path),
                        "--candidate-trace",
                        str(candidate_path),
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertEqual(payload["baseline_report"]["session_id"], "baseline-session")
            self.assertEqual(payload["candidate_report"]["session_id"], "candidate-session")
            self.assertEqual(payload["check"]["status"], "fail")
            self.assertTrue(
                any(item["metric"] == "retrieval_latency_ms_avg" for item in payload["comparison"]["regressions"])
            )


if __name__ == "__main__":
    unittest.main()
