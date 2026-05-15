from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from memfs_doctor.adapters.letta import LettaTraceAdapter
from memfs_doctor.core.metrics import compute_metrics
from memfs_doctor.core.replay import diff_steps, replay_session
from memfs_doctor.reports.render import render_metrics, render_replay, render_sessions
from memfs_doctor.storage.sqlite import SQLiteEventStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memfs-doctor")
    parser.add_argument("--db", default=None, help="Path to the SQLite database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the local SQLite event store.")

    ingest = subparsers.add_parser("ingest", help="Ingest a framework trace file.")
    ingest.add_argument("path", help="Path to a JSONL trace file.")
    ingest.add_argument("--framework", default="letta", choices=["letta"], help="Trace framework.")

    subparsers.add_parser("sessions", help="List captured sessions.")

    subparsers.add_parser("letta-agents", help="List local Letta agents discovered under ~/.letta/agents.")

    ingest_letta_agent = subparsers.add_parser(
        "ingest-letta-agent",
        help="Ingest events reconstructed from a local Letta MemFS git repository.",
    )
    ingest_letta_agent.add_argument("--agent", help="Letta agent identifier under ~/.letta/agents.")
    ingest_letta_agent.add_argument("--memory-dir", help="Explicit path to a Letta memory directory.")

    inspect_cmd = subparsers.add_parser("inspect", help="Inspect a session and basic event info.")
    inspect_cmd.add_argument("--session", required=True, help="Session identifier.")

    metrics_cmd = subparsers.add_parser("metrics", help="Compute metrics for a session.")
    metrics_cmd.add_argument("--session", required=True, help="Session identifier.")
    metrics_cmd.add_argument("--json", action="store_true", help="Render metrics as JSON.")

    replay_cmd = subparsers.add_parser("replay", help="Replay a session timeline.")
    replay_cmd.add_argument("--session", required=True, help="Session identifier.")

    diff_cmd = subparsers.add_parser("diff", help="Diff memory state between two replay steps.")
    diff_cmd.add_argument("--session", required=True, help="Session identifier.")
    diff_cmd.add_argument("--before-step", required=True, type=int)
    diff_cmd.add_argument("--after-step", required=True, type=int)

    return parser


def _store_from_args(args: argparse.Namespace) -> SQLiteEventStore:
    return SQLiteEventStore(args.db)


def _load_adapter(framework: str) -> LettaTraceAdapter:
    if framework == "letta":
        return LettaTraceAdapter()
    raise ValueError(f"Unsupported framework: {framework}")


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
    events = store.get_session_events(session_id)
    if not events:
        raise SystemExit(f"No events found for session {session_id!r}")
    return events


def cmd_inspect(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _require_session_events(store, args.session)
    first = events[0]
    last = events[-1]
    payload = {
        "session_id": args.session,
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
    events = _require_session_events(store, args.session)
    report = compute_metrics(events)
    print(render_metrics(report, as_json=args.json))
    return 0


def cmd_replay(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _require_session_events(store, args.session)
    print(render_replay(replay_session(events)))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    events = _require_session_events(store, args.session)
    print(json.dumps(diff_steps(events, args.before_step, args.after_step), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    command_map = {
        "init-db": cmd_init_db,
        "ingest": cmd_ingest,
        "sessions": cmd_sessions,
        "letta-agents": cmd_letta_agents,
        "ingest-letta-agent": cmd_ingest_letta_agent,
        "inspect": cmd_inspect,
        "metrics": cmd_metrics,
        "replay": cmd_replay,
        "diff": cmd_diff,
    }
    return command_map[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
