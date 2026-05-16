from __future__ import annotations

import json

from memops.core.events import SessionRecord
from memops.core.metrics import MetricsReport
from memops.core.replay import ReplayResult, StepInspection
from memops.core.retrievals import RetrievalInspectionReport
from memops.core.reporting import ComparisonReport, HealthReport


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
    if not result.timeline:
        return "No replayable events found."
    lines = [
        f"Session: {result.session_id}",
        f"Total steps: {result.total_steps}",
        f"First duplicate event: {result.issue_first_seen['duplicate'] or '-'}",
        f"First contradiction event: {result.issue_first_seen['contradiction'] or '-'}",
        f"Final memory count: {result.final_snapshot_memory_count}",
        "Timeline:",
    ]
    for entry in result.timeline:
        flag_suffix = f" flags={','.join(entry.flags)}" if entry.flags else ""
        query_suffix = f" query={entry.query!r}" if entry.query else ""
        lines.append(
            f"{entry.step:03d} {entry.timestamp} {entry.kind} memory={entry.memory_id or '-'} "
            f"snapshot={entry.snapshot_memory_count} {entry.summary}{query_suffix}{flag_suffix}"
        )
    return "\n".join(lines)


def render_step_inspection(result: StepInspection, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(result.to_dict(), indent=2, sort_keys=True)

    delta = result.delta_from_previous
    lines = [
        f"Session: {result.session_id}",
        f"Step: {result.step}/{result.total_steps}",
        f"Summary: {result.summary}",
        f"Flags: {', '.join(result.flags) if result.flags else '-'}",
        f"Snapshot size: {len(result.snapshot)}",
        "Delta from previous step:",
        f"- created: {', '.join(delta['created']) if delta['created'] else '-'}",
        f"- updated: {', '.join(delta['updated']) if delta['updated'] else '-'}",
        f"- deleted: {', '.join(delta['deleted']) if delta['deleted'] else '-'}",
        "Event:",
        json.dumps(result.event, indent=2, sort_keys=True),
    ]
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
    if report.problematic_recalls:
        lines.append("Problematic recalls:")
        for trace in report.problematic_recalls:
            lines.append(
                f"- step={trace.step} memory={trace.memory_id or '-'} stale={trace.stale} "
                f"score={trace.score if trace.score is not None else '-'} tokens={trace.tokens_loaded or 0} "
                f"query={trace.query!r}"
            )
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


def render_retrieval_inspection(report: RetrievalInspectionReport, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(report.to_dict(), indent=2, sort_keys=True)

    lines = [
        f"Session: {report.session_id}",
        f"Framework: {report.framework}",
        f"Agent: {report.agent_id}",
        f"Retrieval count: {report.retrieval_count}",
        f"Miss count: {report.miss_count}",
    ]
    top_problematic = report.to_dict()["top_problematic_recalls"]
    if top_problematic:
        lines.append("Top problematic recalls:")
        for item in top_problematic:
            lines.append(
                f"- step={item['step']} memory={item['memory_id'] or '-'} stale={item['stale']} "
                f"score={item['score'] if item['score'] is not None else '-'} "
                f"tokens={item['tokens_loaded'] or 0} query={item['query']!r}"
            )
    top_pressure = report.to_dict()["top_token_pressure_recalls"]
    if top_pressure:
        lines.append("Top token pressure recalls:")
        for item in top_pressure:
            lines.append(
                f"- step={item['step']} memory={item['memory_id'] or '-'} "
                f"tokens={item['tokens_loaded'] or 0} latency_ms={item['latency_ms'] or 0.0} query={item['query']!r}"
            )
    lines.append("Retrieval traces:")
    for trace in report.traces:
        lines.append(
            f"- step={trace.step} kind={trace.kind} memory={trace.memory_id or '-'} "
            f"cause_step={trace.cause_step or '-'} stale={trace.stale} "
            f"likely_noisy={trace.likely_noisy} query={trace.query!r}"
        )
    return "\n".join(lines)
