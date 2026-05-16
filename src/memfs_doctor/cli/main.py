from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from memfs_doctor.adapters.letta import LettaTraceAdapter
from memfs_doctor.core.metrics import compute_metrics
from memfs_doctor.core.replay import diff_steps, inspect_step, replay_session
from memfs_doctor.core.retrievals import analyze_retrievals, retrieval_trace_for_step, top_problematic_recalls
from memfs_doctor.dashboard.server import create_dashboard_server
from memfs_doctor.core.reporting import (
    HealthReport,
    check_health_report,
    check_regression_report,
    compare_reports,
    evaluate_regressions,
    evaluate_thresholds,
    export_report,
    load_regression_rules,
    load_threshold_rules,
)
from memfs_doctor.reports.render import (
    render_comparison_report,
    render_health_report,
    render_metrics,
    render_replay,
    render_retrieval_inspection,
    render_step_inspection,
    render_sessions,
)
from memfs_doctor.runtime.letta_runtime import (
    LIVE_DEBUG_LOG_ENV,
    RecordedLine,
    default_runtime_trace_path,
    default_structured_trace_path,
    default_transcript_path,
    infer_runtime_events_from_turns,
    load_structured_runtime_events,
    merge_runtime_events,
    parse_transcript_turns,
    record_runtime_trace,
)
from memfs_doctor.storage.sqlite import SQLiteEventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memops")
    parser.add_argument("--db", default=None, help="Path to the SQLite database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the local SQLite event store.")

    ingest = subparsers.add_parser("ingest", help="Ingest a framework trace file.")
    ingest.add_argument("path", help="Path to a JSONL trace file.")
    ingest.add_argument("--framework", default="letta", choices=["letta"], help="Trace framework.")

    subparsers.add_parser("sessions", aliases=["runs"], help="List captured sessions.")
    snapshots_cmd = subparsers.add_parser("health-snapshots", aliases=["shots"], help="List per-turn health snapshots for a session or capture.")
    snapshots_cmd.add_argument("--session", required=True, help="Session or capture identifier.")
    snapshots_cmd.add_argument("--json", action="store_true")

    dashboard_cmd = subparsers.add_parser("dashboard", aliases=["dash"], help="Serve the local memory observability dashboard.")
    dashboard_cmd.add_argument("--host", default="127.0.0.1")
    dashboard_cmd.add_argument("--port", default=8765, type=int)

    subparsers.add_parser("letta-agents", aliases=["agents"], help="List local Letta agents discovered under ~/.letta/agents.")

    subparsers.add_parser("letta-captures", aliases=["captures"], help="List pending Letta session captures.")

    start_letta_capture = subparsers.add_parser(
        "start-letta-capture",
        aliases=["capture"],
        help="Start a bounded capture window for a real Letta session.",
    )
    start_letta_capture.add_argument("--agent", help="Letta agent identifier under ~/.letta/agents. Defaults to the active Letta agent.")
    start_letta_capture.add_argument("--memory-dir", help="Explicit path to a Letta memory directory.")

    record_letta_runtime = subparsers.add_parser(
        "record-letta-runtime",
        aliases=["record"],
        help="Run Letta through a terminal recorder and emit a runtime JSONL trace for the active capture.",
    )
    record_letta_runtime.add_argument(
        "--capture-id",
        help="Active capture id returned by start-letta-capture. Defaults to the latest pending capture.",
    )
    record_letta_runtime.add_argument(
        "--trace-path",
        help="Optional output path for the runtime JSONL trace. Defaults to .memfs_doctor/runtime/<capture-id>.jsonl",
    )
    record_letta_runtime.add_argument(
        "--structured-trace-path",
        help="Optional structured retrieval sidecar path. Defaults to .memfs_doctor/runtime/<capture-id>.structured.jsonl",
    )
    record_letta_runtime.add_argument(
        "--auto-finish",
        action="store_true",
        help="Finish the capture and ingest the merged session automatically after the wrapped command exits.",
    )
    record_letta_runtime.add_argument(
        "runtime_command",
        nargs=argparse.REMAINDER,
        help="Command to run after --, for example: -- letta",
    )

    chat_cmd = subparsers.add_parser(
        "chat",
        help="Start capture, run a wrapped Letta session, and auto-finish it in one command.",
    )
    chat_cmd.add_argument("--agent", help="Letta agent identifier under ~/.letta/agents. Defaults to the active Letta agent.")
    chat_cmd.add_argument("--memory-dir", help="Explicit path to a Letta memory directory.")
    chat_cmd.add_argument(
        "--trace-path",
        help="Optional output path for the runtime JSONL trace. Defaults to .memfs_doctor/runtime/<capture-id>.jsonl",
    )
    chat_cmd.add_argument(
        "--structured-trace-path",
        help="Optional structured retrieval sidecar path. Defaults to .memfs_doctor/runtime/<capture-id>.structured.jsonl",
    )
    chat_cmd.add_argument(
        "runtime_command",
        nargs=argparse.REMAINDER,
        help="Command to run after --, for example: -- letta",
    )

    finish_letta_capture = subparsers.add_parser(
        "finish-letta-capture",
        aliases=["finish"],
        help="Finish a bounded Letta session capture and ingest events into the local store.",
    )
    finish_letta_capture.add_argument(
        "--capture-id",
        help="Capture id returned by start-letta-capture. Defaults to the latest pending capture.",
    )
    finish_letta_capture.add_argument(
        "--runtime-trace",
        help="Optional Letta runtime JSONL trace to merge retrievals, misses, and timing metadata into the captured session.",
    )

    ingest_letta_agent = subparsers.add_parser(
        "ingest-letta-agent",
        help="Ingest events reconstructed from a local Letta memory git repository.",
    )
    ingest_letta_agent.add_argument("--agent", help="Letta agent identifier under ~/.letta/agents.")
    ingest_letta_agent.add_argument("--memory-dir", help="Explicit path to a Letta memory directory.")

    inspect_cmd = subparsers.add_parser("inspect", aliases=["session"], help="Inspect a session and basic event info.")
    inspect_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")

    metrics_cmd = subparsers.add_parser("metrics", aliases=["stats"], help="Compute metrics for a session.")
    metrics_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    metrics_cmd.add_argument("--json", action="store_true", help="Render metrics as JSON.")

    report_cmd = subparsers.add_parser("report", aliases=["health"], help="Generate a health report for a session.")
    report_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    report_cmd.add_argument("--thresholds", help="Optional JSON threshold config path.")
    report_cmd.add_argument("--json", action="store_true", help="Render report as JSON.")
    report_cmd.add_argument("--out", help="Optional path to export the report JSON.")

    check_session_cmd = subparsers.add_parser("check-session", aliases=["gate"], help="Fail with a non-zero exit code when a session breaches memory health thresholds.")
    check_session_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    check_session_cmd.add_argument("--thresholds", help="Optional JSON threshold config path.")
    check_session_cmd.add_argument("--fail-on", choices=["error", "warning"], default="error")
    check_session_cmd.add_argument("--json", action="store_true", help="Render check result as JSON.")
    check_session_cmd.add_argument("--out", help="Optional path to export the check result JSON.")

    compare_cmd = subparsers.add_parser("compare-sessions", aliases=["compare"], help="Compare two session health reports.")
    compare_cmd.add_argument("--baseline", help="Baseline session identifier. Defaults to the second-latest stored session.")
    compare_cmd.add_argument("--candidate", help="Candidate session identifier. Defaults to the latest stored session.")
    compare_cmd.add_argument("--regression-thresholds", help="Optional JSON regression threshold config path.")
    compare_cmd.add_argument("--json", action="store_true", help="Render comparison as JSON.")
    compare_cmd.add_argument("--out", help="Optional path to export the comparison JSON.")

    check_regression_cmd = subparsers.add_parser("check-regression", aliases=["regress"], help="Fail with a non-zero exit code when candidate memory health regresses beyond tolerance.")
    check_regression_cmd.add_argument("--baseline", help="Baseline session identifier. Defaults to the second-latest stored session.")
    check_regression_cmd.add_argument("--candidate", help="Candidate session identifier. Defaults to the latest stored session.")
    check_regression_cmd.add_argument("--regression-thresholds", help="Optional JSON regression threshold config path.")
    check_regression_cmd.add_argument("--fail-on", choices=["error", "warning"], default="error")
    check_regression_cmd.add_argument("--json", action="store_true", help="Render check result as JSON.")
    check_regression_cmd.add_argument("--out", help="Optional path to export the check result JSON.")

    retrieval_cmd = subparsers.add_parser("inspect-retrieval", aliases=["retrieval"], help="Inspect retrieval causality and recall quality.")
    retrieval_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    retrieval_cmd.add_argument("--step", type=int, help="Optional retrieval step to inspect as a single JSON object.")
    retrieval_cmd.add_argument("--json", action="store_true", help="Render inspection as JSON.")

    replay_cmd = subparsers.add_parser("replay", aliases=["timeline"], help="Replay a session timeline.")
    replay_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    replay_cmd.add_argument("--trace-path", help="Optional trace file path for offline replay instead of a stored session.")
    replay_cmd.add_argument("--framework", default="letta", choices=["letta"], help="Trace framework for --trace-path.")
    replay_cmd.add_argument("--json", action="store_true", help="Render replay as JSON.")

    step_cmd = subparsers.add_parser("inspect-step", aliases=["step"], help="Inspect a specific replay step and memory state.")
    step_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session.")
    step_cmd.add_argument("--trace-path", help="Optional trace file path for offline step inspection.")
    step_cmd.add_argument("--framework", default="letta", choices=["letta"], help="Trace framework for --trace-path.")
    step_cmd.add_argument("--step", required=True, type=int, help="1-based replay step number.")
    step_cmd.add_argument("--json", action="store_true", help="Render inspection as JSON.")

    diff_cmd = subparsers.add_parser("diff", help="Diff memory state between two replay steps.")
    diff_cmd.add_argument("--session", help="Session identifier. Defaults to the latest stored session unless --trace-path is used.")
    diff_cmd.add_argument("--trace-path", help="Optional trace file path for offline diffing.")
    diff_cmd.add_argument("--framework", default="letta", choices=["letta"], help="Trace framework for --trace-path.")
    diff_cmd.add_argument("--before-step", required=True, type=int)
    diff_cmd.add_argument("--after-step", required=True, type=int)
    diff_cmd.add_argument("--json", action="store_true", help="Render diff as JSON.")

    return parser


def _store_from_args(args: argparse.Namespace) -> SQLiteEventStore:
    return SQLiteEventStore(args.db)


def _load_adapter(framework: str) -> LettaTraceAdapter:
    if framework == "letta":
        return LettaTraceAdapter()
    raise ValueError(f"Unsupported framework: {framework}")


def _resolve_session_id(store: SQLiteEventStore, session_id: str | None) -> str:
    if session_id:
        return session_id
    latest = store.latest_session_ids(1)
    if not latest:
        raise SystemExit("No stored sessions found.")
    return latest[0]


def _resolve_comparison_session_ids(
    store: SQLiteEventStore,
    baseline: str | None,
    candidate: str | None,
) -> tuple[str, str]:
    if baseline and candidate:
        return baseline, candidate
    latest_two = store.latest_session_ids(2)
    if len(latest_two) < 2:
        raise SystemExit("Need at least two stored sessions to compare.")
    return baseline or latest_two[1], candidate or latest_two[0]


def _resolve_capture_id(adapter: LettaTraceAdapter, capture_id: str | None) -> str:
    if capture_id:
        return capture_id
    latest = adapter.latest_capture()
    if latest is None:
        raise SystemExit("No pending Letta captures found.")
    return latest.capture_id


def cmd_init_db(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.init_db()
    print(f"Initialized database at {store.db_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.init_db()
    adapter = _load_adapter(args.framework)
    events = adapter.load_events(args.path)
    count = store.ingest_events(events)
    print(f"Ingested {count} events from {Path(args.path)}")
    return 0


def cmd_sessions(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    print(render_sessions(store.list_sessions()))
    return 0


def cmd_health_snapshots(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    snapshots = store.list_health_snapshots(args.session)
    if args.json:
        print(json.dumps({"snapshots": snapshots}, indent=2, sort_keys=True))
        return 0
    if not snapshots:
        print("No health snapshots found.")
        return 0
    for item in snapshots:
        print(
            f"turn={item['turn_index']} status={item['status']} query={item['query']!r} "
            f"updated_at={item['updated_at']}"
        )
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.init_db()
    server = create_dashboard_server(args.host, args.port, store=store)
    print(f"MemOps dashboard listening on http://{args.host}:{args.port}")
    print(f"Dashboard database: {store.db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
    finally:
        server.server_close()
    return 0


def cmd_letta_agents(args: argparse.Namespace) -> int:
    del args
    adapter = LettaTraceAdapter()
    agents = adapter.discover_agents()
    if not agents:
        print("No local Letta agents found.")
        return 0
    for agent in agents:
        print(f"{agent.agent_id} memory_dir={agent.memory_dir}")
    return 0


def cmd_letta_captures(args: argparse.Namespace) -> int:
    del args
    adapter = LettaTraceAdapter()
    captures = adapter.list_captures()
    if not captures:
        print("No pending Letta captures.")
        return 0
    for capture in captures:
        print(
            f"{capture.capture_id} agent={capture.agent_id} conversation={capture.conversation_id} "
            f"started={capture.started_at} base_head={capture.base_head[:12]}"
        )
    return 0


def cmd_start_letta_capture(args: argparse.Namespace) -> int:
    adapter = LettaTraceAdapter()
    capture = adapter.start_session_capture(agent_id=args.agent, memory_dir=args.memory_dir)
    print(
        f"Started Letta capture {capture.capture_id} agent={capture.agent_id} "
        f"conversation={capture.conversation_id} base_head={capture.base_head[:12]}"
    )
    return 0


def _run_wrapped_capture(
    *,
    store: SQLiteEventStore,
    adapter: LettaTraceAdapter,
    capture,
    runtime_command: list[str],
    trace_path_arg: str | None,
    structured_trace_path_arg: str | None,
    auto_finish: bool,
) -> int:
    command = list(runtime_command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        command = ["letta"]

    output_path = Path(trace_path_arg) if trace_path_arg else default_runtime_trace_path(Path.cwd(), capture.capture_id)
    structured_trace_path = (
        Path(structured_trace_path_arg)
        if structured_trace_path_arg
        else default_structured_trace_path(Path.cwd(), capture.capture_id)
    )
    transcript_path = default_transcript_path(Path.cwd(), capture.capture_id)
    debug_log_path = Path.cwd() / ".memfs_doctor" / "dashboard" / f"{capture.capture_id}.live-errors.log"
    store.init_db()

    def handle_turn(*, turn, turns, lines) -> None:
        del lines
        heuristic_events = infer_runtime_events_from_turns(
            turns,
            agent_id=capture.agent_id,
            session_id=capture.capture_id,
        )
        structured_events = load_structured_runtime_events(
            structured_trace_path,
            agent_id=capture.agent_id,
            session_id=capture.capture_id,
        )
        runtime_events = merge_runtime_events(heuristic_events, structured_events)
        preview_events = adapter.preview_session_capture(
            capture.capture_id,
            runtime_events=runtime_events,
        )
        report = _health_report_from_events(preview_events)
        store.upsert_health_snapshot(
            capture_id=capture.capture_id,
            session_id=capture.capture_id,
            framework=report.framework,
            agent_id=report.agent_id,
            turn_index=len(turns),
            query=turn.query,
            status=report.status,
            updated_at=turn.response_timestamp or turn.query_timestamp,
            metrics=report.metrics,
            findings=[item.to_dict() for item in report.findings],
        )

    exit_code, trace_path, raw_transcript_path, events = record_runtime_trace(
        agent_id=capture.agent_id,
        session_id=capture.capture_id,
        command=command,
        output_path=output_path,
        transcript_path=transcript_path,
        structured_trace_path=structured_trace_path,
        on_turn=handle_turn,
        env_extra={LIVE_DEBUG_LOG_ENV: str(debug_log_path)},
        debug_log_path=str(debug_log_path),
    )

    _backfill_health_snapshots(
        store=store,
        adapter=adapter,
        capture=capture,
        transcript_path=raw_transcript_path,
        structured_trace_path=structured_trace_path,
    )
    snapshot_count = store.count_health_snapshots(capture.capture_id)
    reopened_snapshot_count = SQLiteEventStore(store.db_path).count_health_snapshots(capture.capture_id)
    print(f"\nWrote raw transcript to {raw_transcript_path}")
    print(f"Wrote runtime trace to {trace_path} with {len(events)} inferred events.")
    print(f"Using database {store.db_path}")
    print(f"Persisted {snapshot_count} health snapshots for {capture.capture_id}")
    print(f"Reopened database sees {reopened_snapshot_count} health snapshots for {capture.capture_id}")

    if auto_finish:
        merged_events = adapter.finish_session_capture(capture.capture_id, runtime_trace_path=trace_path)
        ingested = store.ingest_events(merged_events)
        print(f"Ingested {ingested} events from Letta session capture {capture.capture_id}")
        post_finish_snapshot_count = SQLiteEventStore(store.db_path).count_health_snapshots(capture.capture_id)
        print(f"Post-finish database sees {post_finish_snapshot_count} health snapshots for {capture.capture_id}")

    return exit_code


def cmd_record_letta_runtime(args: argparse.Namespace) -> int:
    adapter = LettaTraceAdapter()
    resolved_capture_id = _resolve_capture_id(adapter, args.capture_id)
    capture = next((item for item in adapter.list_captures() if item.capture_id == resolved_capture_id), None)
    if capture is None:
        raise SystemExit(f"Unknown capture id: {resolved_capture_id}")

    store = _store_from_args(args)
    return _run_wrapped_capture(
        store=store,
        adapter=adapter,
        capture=capture,
        runtime_command=args.runtime_command,
        trace_path_arg=args.trace_path,
        structured_trace_path_arg=args.structured_trace_path,
        auto_finish=args.auto_finish,
    )


def cmd_chat(args: argparse.Namespace) -> int:
    adapter = LettaTraceAdapter()
    capture = adapter.start_session_capture(agent_id=args.agent, memory_dir=args.memory_dir)
    print(
        f"Started Letta capture {capture.capture_id} agent={capture.agent_id} "
        f"conversation={capture.conversation_id} base_head={capture.base_head[:12]}"
    )
    store = _store_from_args(args)
    return _run_wrapped_capture(
        store=store,
        adapter=adapter,
        capture=capture,
        runtime_command=args.runtime_command,
        trace_path_arg=args.trace_path,
        structured_trace_path_arg=args.structured_trace_path,
        auto_finish=True,
    )


def cmd_finish_letta_capture(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.init_db()
    adapter = LettaTraceAdapter()
    resolved_capture_id = _resolve_capture_id(adapter, args.capture_id)
    events = adapter.finish_session_capture(resolved_capture_id, runtime_trace_path=args.runtime_trace)
    count = store.ingest_events(events)
    print(f"Ingested {count} events from Letta session capture {resolved_capture_id}")
    return 0


def cmd_ingest_letta_agent(args: argparse.Namespace) -> int:
    if not args.agent and not args.memory_dir:
        raise SystemExit("Provide --agent <id> or --memory-dir <path>.")

    store = _store_from_args(args)
    store.init_db()
    adapter = LettaTraceAdapter()
    if args.memory_dir:
        events = adapter.load_events_from_memory_repo(args.memory_dir)
        target = args.memory_dir
    else:
        events = adapter.load_events_from_agent(args.agent)
        target = args.agent
    count = store.ingest_events(events)
    print(f"Ingested {count} events from Letta memory source {target}")
    return 0


def _require_session_events(store: SQLiteEventStore, session_id: str):
    resolved_session_id = _resolve_session_id(store, session_id)
    events = store.get_session_events(resolved_session_id)
    if not events:
        raise SystemExit(f"No events found for session {resolved_session_id!r}")
    return events


def _load_events_for_replay(
    store: SQLiteEventStore,
    *,
    session_id: str | None,
    trace_path: str | None,
    framework: str,
):
    if trace_path:
        adapter = _load_adapter(framework)
        events = adapter.load_events(trace_path)
        if not events:
            raise SystemExit(f"No events found in trace file {trace_path!r}")
        return events
    resolved_session_id = _resolve_session_id(store, session_id)
    return _require_session_events(store, resolved_session_id)


def cmd_inspect(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    resolved_session_id = _resolve_session_id(store, args.session)
    events = _require_session_events(store, resolved_session_id)
    first = events[0]
    last = events[-1]
    payload = {
        "session_id": resolved_session_id,
        "framework": first.framework,
        "agent_id": first.agent_id,
        "event_count": len(events),
        "started_at": first.timestamp,
        "ended_at": last.timestamp,
        "event_kinds": [event.kind.value for event in events],
    }
    print(json.dumps(payload, indent=2))
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    resolved_session_id = _resolve_session_id(store, args.session)
    events = _require_session_events(store, resolved_session_id)
    report = compute_metrics(events)
    print(render_metrics(report, as_json=args.json))
    return 0


def _health_report_for_session(
    store: SQLiteEventStore,
    session_id: str,
    *,
    threshold_path: str | None = None,
) -> HealthReport:
    events = _require_session_events(store, session_id)
    metrics = compute_metrics(events)
    findings = evaluate_thresholds(metrics, load_threshold_rules(threshold_path))
    retrievals = analyze_retrievals(events)
    return HealthReport.from_metrics(metrics, findings, problematic_recalls=top_problematic_recalls(retrievals.traces))


def _health_report_from_events(events, *, threshold_path: str | None = None) -> HealthReport:
    metrics = compute_metrics(events)
    findings = evaluate_thresholds(metrics, load_threshold_rules(threshold_path))
    retrievals = analyze_retrievals(events)
    return HealthReport.from_metrics(metrics, findings, problematic_recalls=top_problematic_recalls(retrievals.traces))


def _load_recorded_lines(path: str | Path) -> list[RecordedLine]:
    lines: list[RecordedLine] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if "\t" not in raw:
            continue
        timestamp, text = raw.split("\t", 1)
        lines.append(RecordedLine(timestamp=timestamp, text=text))
    return lines


def _backfill_health_snapshots(
    *,
    store: SQLiteEventStore,
    adapter: LettaTraceAdapter,
    capture,
    transcript_path: str | Path,
    structured_trace_path: str | Path,
) -> None:
    existing = store.list_health_snapshots(capture.capture_id)
    existing_turns = {item["turn_index"] for item in existing}
    turns = parse_transcript_turns(_load_recorded_lines(transcript_path))
    structured_events = load_structured_runtime_events(
        structured_trace_path,
        agent_id=capture.agent_id,
        session_id=capture.capture_id,
    )
    for index in range(1, len(turns) + 1):
        if index in existing_turns:
            continue
        partial_turns = turns[:index]
        heuristic_events = infer_runtime_events_from_turns(
            partial_turns,
            agent_id=capture.agent_id,
            session_id=capture.capture_id,
        )
        runtime_events = merge_runtime_events(heuristic_events, structured_events)
        preview_events = adapter.preview_session_capture(
            capture.capture_id,
            runtime_events=runtime_events,
        )
        report = _health_report_from_events(preview_events)
        turn = partial_turns[-1]
        store.upsert_health_snapshot(
            capture_id=capture.capture_id,
            session_id=capture.capture_id,
            framework=report.framework,
            agent_id=report.agent_id,
            turn_index=index,
            query=turn.query,
            status=report.status,
            updated_at=turn.response_timestamp or turn.query_timestamp,
            metrics=report.metrics,
            findings=[item.to_dict() for item in report.findings],
        )


def cmd_report(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    resolved_session_id = _resolve_session_id(store, args.session)
    report = _health_report_for_session(store, resolved_session_id, threshold_path=args.thresholds)
    if args.out:
        export_report(args.out, report.to_dict())
    print(render_health_report(report, as_json=args.json))
    return 0


def cmd_check_session(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    resolved_session_id = _resolve_session_id(store, args.session)
    report = _health_report_for_session(store, resolved_session_id, threshold_path=args.thresholds)
    result = check_health_report(report, fail_on=args.fail_on)
    if args.out:
        export_report(args.out, result.to_dict())
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(result.summary)
    return result.exit_code


def cmd_compare_sessions(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    baseline_id, candidate_id = _resolve_comparison_session_ids(store, args.baseline, args.candidate)
    baseline = _health_report_for_session(store, baseline_id)
    candidate = _health_report_for_session(store, candidate_id)
    comparison = compare_reports(baseline, candidate)
    if args.regression_thresholds:
        payload = {
            **comparison.to_dict(),
            "regression_findings": [
                item.to_dict() for item in evaluate_regressions(comparison, load_regression_rules(args.regression_thresholds))
            ],
        }
    else:
        payload = comparison.to_dict()
    if args.out:
        export_report(args.out, payload)
    if args.json and args.regression_thresholds:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(render_comparison_report(comparison, as_json=args.json))
    return 0


def cmd_check_regression(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    baseline_id, candidate_id = _resolve_comparison_session_ids(store, args.baseline, args.candidate)
    baseline = _health_report_for_session(store, baseline_id)
    candidate = _health_report_for_session(store, candidate_id)
    comparison = compare_reports(baseline, candidate)
    findings = evaluate_regressions(comparison, load_regression_rules(args.regression_thresholds))
    result = check_regression_report(comparison, findings, fail_on=args.fail_on)
    if args.out:
        export_report(args.out, result.to_dict())
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(result.summary)
    return result.exit_code


def cmd_inspect_retrieval(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    resolved_session_id = _resolve_session_id(store, args.session)
    events = _require_session_events(store, resolved_session_id)
    if args.step is not None:
        trace = retrieval_trace_for_step(events, args.step)
        print(json.dumps(trace.to_dict(), indent=2, sort_keys=True))
        return 0
    print(render_retrieval_inspection(analyze_retrievals(events), as_json=args.json))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _load_events_for_replay(
        store,
        session_id=args.session,
        trace_path=args.trace_path,
        framework=args.framework,
    )
    replay = replay_session(events)
    if args.json:
        print(json.dumps(replay.to_dict(), indent=2, sort_keys=True))
        return 0
    print(render_replay(replay))
    return 0


def cmd_inspect_step(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _load_events_for_replay(
        store,
        session_id=args.session,
        trace_path=args.trace_path,
        framework=args.framework,
    )
    print(render_step_inspection(inspect_step(events, args.step), as_json=args.json))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _load_events_for_replay(
        store,
        session_id=args.session,
        trace_path=args.trace_path,
        framework=args.framework,
    )
    print(json.dumps(diff_steps(events, args.before_step, args.after_step), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command_map = {
        "init-db": cmd_init_db,
        "ingest": cmd_ingest,
        "sessions": cmd_sessions,
        "runs": cmd_sessions,
        "health-snapshots": cmd_health_snapshots,
        "shots": cmd_health_snapshots,
        "dashboard": cmd_dashboard,
        "dash": cmd_dashboard,
        "letta-agents": cmd_letta_agents,
        "agents": cmd_letta_agents,
        "letta-captures": cmd_letta_captures,
        "captures": cmd_letta_captures,
        "start-letta-capture": cmd_start_letta_capture,
        "capture": cmd_start_letta_capture,
        "record-letta-runtime": cmd_record_letta_runtime,
        "record": cmd_record_letta_runtime,
        "chat": cmd_chat,
        "finish-letta-capture": cmd_finish_letta_capture,
        "finish": cmd_finish_letta_capture,
        "ingest-letta-agent": cmd_ingest_letta_agent,
        "inspect": cmd_inspect,
        "session": cmd_inspect,
        "metrics": cmd_metrics,
        "stats": cmd_metrics,
        "report": cmd_report,
        "health": cmd_report,
        "check-session": cmd_check_session,
        "gate": cmd_check_session,
        "compare-sessions": cmd_compare_sessions,
        "compare": cmd_compare_sessions,
        "check-regression": cmd_check_regression,
        "regress": cmd_check_regression,
        "inspect-retrieval": cmd_inspect_retrieval,
        "retrieval": cmd_inspect_retrieval,
        "replay": cmd_replay,
        "timeline": cmd_replay,
        "inspect-step": cmd_inspect_step,
        "step": cmd_inspect_step,
        "diff": cmd_diff,
    }
    return command_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
