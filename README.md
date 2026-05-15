# MemFS Doctor

MemFS Doctor is a Python-first observability and replay toolkit for persistent AI memory systems.

Current implementation focus:

- normalized memory event capture
- local trace storage
- metrics for memory health
- deterministic session replay
- Letta-first adapter scaffolding
- local Letta agent discovery
- git-history import from real Letta MemFS repos
- bounded start/finish capture for real Letta sessions
- interactive runtime trace recording for Letta terminal sessions

## Testing

Testing is a project gate, not a cleanup step after the fact.

- automated and manual validation expectations live in `docs/testing.md`
- every implementation step should add or update tests before we move ahead

## Quick Start

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --help
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
```

## Example Flow

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main ingest examples/letta_session.jsonl --framework letta
PYTHONPATH=src python3 -m memfs_doctor.cli.main inspect --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main metrics --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main replay --session session-001
```

## Local Letta Import

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-letta.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-letta.db ingest-letta-agent --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-letta.db sessions
```

## Real Letta Session Capture

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
# run a real Letta conversation here
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-captures
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture --capture-id <capture-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db sessions
```

## Runtime Trace Augmentation

If you have a Letta runtime JSONL trace with retrieval and miss events, merge it into the bounded session:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture \
  --capture-id <capture-id> \
  --runtime-trace <path-to-runtime-trace.jsonl>
```

## Wrapped Letta Runtime Recording

You can also have MemFS Doctor generate the runtime trace for a terminal Letta session automatically:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db record-letta-runtime \
  --capture-id <capture-id> \
  --auto-finish \
  -- letta
```

This wrapper:

- runs the terminal Letta command
- records transcript lines
- infers retrieval and retrieval-miss events from the conversation flow
- writes a runtime JSONL trace under `.memfs_doctor/runtime/`
- optionally auto-finishes the bounded session capture into SQLite

## Current State

This version establishes the Phase 1 foundation and the start of the Letta adapter path:

- append-only normalized event model
- SQLite-backed local event store
- snapshot reconstruction from events
- terminal reports for inspect, metrics, and replay
- Letta JSONL trace ingestion scaffold
