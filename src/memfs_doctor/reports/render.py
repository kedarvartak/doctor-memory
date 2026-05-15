from __future__ import annotations

import json

from memfs_doctor.core.events import SessionRecord
from memfs_doctor.core.metrics import MetricsReport
from memfs_doctor.core.replay import ReplayResult


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

