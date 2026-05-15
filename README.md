# MemFS Doctor

MemFS Doctor is a Python-first observability and replay toolkit for persistent AI memory systems.

Current implementation focus:

- normalized memory event capture
- local trace storage
- metrics for memory health
- deterministic session replay
- Letta-first adapter scaffolding

## Testing

Testing is a project gate, not a cleanup step after the fact.

- automated and manual validation expectations live in `docs/testing.md`
- every implementation step should add or update tests before we move ahead

## Quick Start

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --help
```

## Example Flow

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main ingest examples/letta_session.jsonl --framework letta
PYTHONPATH=src python3 -m memfs_doctor.cli.main inspect --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main metrics --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main replay --session session-001
```

## Current State

This version establishes the Phase 1 foundation and the start of the Letta adapter path:

- append-only normalized event model
- SQLite-backed local event store
- snapshot reconstruction from events
- terminal reports for inspect, metrics, and replay
- Letta JSONL trace ingestion scaffold
