from __future__ import annotations

import json

from memfs_doctor.core.events import SessionRecord
from memfs_doctor.core.metrics import MetricsReport
from memfs_doctor.core.replay import ReplayResult
from memfs_doctor.core.reporting import ComparisonReport, HealthReport


def render_sessions(sessions: list[SessionRecord]) -> str:
    if not sessions:
        return "No sessions found."
    lines = []
    for session in sessions:
        lines.append(
            f"{session.session_id} framework={session.framework} agent={session.agent_id} "
            f"events={session.event_count} started={session.started_at or '-'} ended={session.ended_at or '-'}"
        )
    return "\n".join(lines)


def render_metrics(report: MetricsReport, as_json: bool = False) -> str:
    payload = {
        "session_id": report.session_id,
        "framework": report.framework,
        "agent_id": report.agent_id,
        "metrics": report.values,
    }
    if as_json:
        return json.dumps(payload, indent=2, sort_keys=True)

    lines = [
        f"Session: {report.session_id}",
        f"Framework: {report.framework}",
        f"Agent: {report.agent_id}",
    ]
    for key, value in report.values.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def render_replay(result: ReplayResult) -> str:
    lines = [
        f"Session: {result.session_id}",
        f"Total steps: {result.total_steps}",
        f"First duplicate event: {result.issue_first_seen['duplicate'] or '-'}",
        f"First contradiction event: {result.issue_first_seen['contradiction'] or '-'}",
        "Timeline:",
    ]
    lines.extend(result.timeline)
    return "\n".join(lines)


def render_health_report(report: HealthReport, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), indent=2, sort_keys=True)

    lines = [
        f"Session: {report.session_id}",
        f"Framework: {report.framework}",
        f"Agent: {report.agent_id}",
        f"Status: {report.status}",
        "Metrics:",
    ]
    for key, value in report.metrics.items():
        lines.append(f"- {key}: {value}")
    if report.findings:
        lines.append("Findings:")
        for finding in report.findings:
            lines.append(f"- [{finding.severity}] {finding.metric}: {finding.message}")
    return "\n".join(lines)


def render_comparison_report(report: ComparisonReport, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), indent=2, sort_keys=True)

    lines = [
        f"Baseline: {report.baseline_session_id}",
        f"Candidate: {report.candidate_session_id}",
        f"Regression count: {report.regression_count}",
        "Deltas:",
    ]
    for metric, payload in report.deltas.items():
        lines.append(
            f"- {metric}: baseline={payload['baseline']} candidate={payload['candidate']} delta={payload['delta']}"
        )
    if report.regressions:
        lines.append("Regressions:")
        for item in report.regressions:
            lines.append(
                f"- {item['metric']}: baseline={item['baseline']} candidate={item['candidate']} delta={item['delta']}"
            )
    return "\n".join(lines)
