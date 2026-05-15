<h1 align="center">MemFS Doctor</h1>

<p align="center">
  Observability, replay, and regression analysis for persistent AI memory systems.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/CLI-First-1F2937" alt="CLI First">
  <img src="https://img.shields.io/badge/SQLite-Trace%20Store-003B57?logo=sqlite&logoColor=white" alt="SQLite Trace Store">
  <img src="https://img.shields.io/badge/Letta-Adapter%20First-0F766E" alt="Letta Adapter First">
  <img src="https://img.shields.io/badge/Status-Phase%205%20Implemented-15803D" alt="Status Phase 5 Implemented">
</p>

<p align="center">
  <img src="examples/banner.png" alt="MemFS Doctor banner">
</p>

## What MemFS Doctor Is

MemFS Doctor is a Python-first developer tool for inspecting, measuring, and comparing the memory behavior of AI agents that persist information across sessions.

The product exists to answer a practical problem: once an agent has memory, it can fail in subtle ways that are hard to diagnose. It may retrieve nothing when it should remember, retrieve the wrong thing, rewrite memory too aggressively, carry stale facts forward, or become slow under memory pressure. Most teams can feel these problems during testing, but they lack a durable way to capture what happened, replay it, and compare one run against another.

MemFS Doctor is built to close that gap. It turns raw memory activity into a normalized event stream, stores it locally, reconstructs session history, computes memory-health metrics, and produces reports that make baseline-versus-candidate evaluation concrete.

## Why This Product Exists

Traditional observability stacks are strong at API latency, logs, and infrastructure health. They are weak at answering memory-specific questions for agent systems:

- Why did the agent miss a fact it should have known?
- Did retrieval quality get worse after a prompt or runtime change?
- Is the agent rewriting memory too often?
- Are memory recalls slow, empty, noisy, or stale?
- Did the latest candidate regress against the previous known-good behavior?

MemFS Doctor treats agent memory as a system that deserves the same rigor as any other production subsystem. The goal is not only to collect traces, but to make those traces actionable for debugging, evaluation, and release decisions.

## Product Goal

The long-term goal is to become a practical observability layer for persistent AI memory:

- capture memory activity from real agent frameworks
- normalize events into a framework-neutral schema
- replay memory evolution across a session
- score memory health with stable metrics
- compare baseline and candidate runs for regressions
- help developers explain why memory behavior changed

The current implementation is CLI-first and Letta-first by design. That keeps the product grounded in real workflows before expanding into broader adapters or a dedicated dashboard.

## Core Idea

MemFS Doctor sits between raw framework behavior and developer judgment.

Instead of relying on intuition like "this run felt worse," it gives you a repeatable pipeline:

1. Capture or ingest a real session trace.
2. Store the trace as normalized append-only memory events.
3. Reconstruct what the memory state looked like over time.
4. Compute memory-health metrics for the session.
5. Generate a report with threshold findings.
6. Compare two sessions to surface regressions.

This makes memory behavior testable in the same way teams already test latency, correctness, and reliability.

## What It Measures Today

The current metrics layer focuses on early indicators of unhealthy memory behavior:

- `retrieval_latency_ms_avg`
- `memory_tokens_loaded_total`
- `context_pressure_score`
- `memory_churn_rate`
- `duplicate_rate`
- `contradiction_score`
- `stale_recall_rate`
- `empty_retrieval_rate`

These metrics are designed to run on stored traces, not only live sessions. That matters because serious debugging and evaluation usually happens after a run, not during it.

## Current Capabilities

- normalized append-only memory event model
- local SQLite-backed trace storage
- deterministic snapshot reconstruction from events
- terminal inspection, metrics, replay, and reporting flows
- Letta session capture and runtime recording support
- health reports with threshold findings
- baseline-versus-candidate session comparison
- retrieval-path inspection and problematic recall surfacing
- step-by-step memory replay and snapshot diff inspection
- offline replay from stored trace files without the SQLite store
- JSON export suitable for downstream automation

## Who This Is For

- teams building agents with persistent memory
- developers evaluating retrieval quality across changes
- researchers testing memory behavior under stress
- anyone who needs more than transcripts to understand why an agent remembered, forgot, or slowed down

## Installation

MemFS Doctor currently runs as a local Python package.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or run directly from the repository with:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --help
```

Requirements:

- Python `3.11+`
- local access to the repository
- Letta installed locally if you want to use the Letta capture workflow

## Quick Start

Initialize a local database and inspect the CLI:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --help
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
```

## Example Workflow

Ingest a trace, inspect it, compute metrics, and replay the session:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db ingest examples/letta_session.jsonl --framework letta
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db inspect --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db metrics --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor.db replay --session session-001
```

## Real Letta Session Capture

MemFS Doctor can capture real Letta sessions into the local event store.

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
# run a real Letta conversation here
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-captures
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture --capture-id <capture-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db sessions
```

If you already have a runtime JSONL trace with retrieval and miss events, merge it into the bounded session:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture \
  --capture-id <capture-id> \
  --runtime-trace <path-to-runtime-trace.jsonl>
```

## Wrapped Runtime Recording

MemFS Doctor can also generate the runtime trace for a terminal Letta session automatically:

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
- can auto-finish the bounded session into SQLite

## Health Reports And Regression Comparison

Generate a per-session health report:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db report \
  --session <session-id> \
  --json
```

Compare a candidate run against a baseline:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db compare-sessions \
  --baseline <baseline-session-id> \
  --candidate <candidate-session-id> \
  --json
```

This is the core evaluation loop for the product. A healthy baseline and a stressed or modified candidate should produce directionally correct differences in metrics such as retrieval latency, empty retrieval rate, and memory churn.

Inspect retrieval causality and recall quality for a stored session:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect-retrieval \
  --session <session-id> \
  --json
```

Inspect a single retrieval step:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect-retrieval \
  --session <session-id> \
  --step <retrieval-step>
```

## Development Philosophy

MemFS Doctor is being built with a narrow, deliberate scope:

- Python-first
- framework-neutral at the core
- Letta-first as the initial adapter
- local and inspectable before distributed and abstract
- test-gated at every phase

The project treats testing as a product requirement, not a cleanup step. Manual and automated validation expectations live in `docs/testing.md`.

## Roadmap Status

The project has completed the first reporting-oriented milestone needed to make memory behavior measurable:

- Phase 1: core event model and local storage
- Phase 2: Letta adapter MVP and capture workflow
- Phase 3: metrics, health reports, and session comparison
- Phase 4: retrieval explainability and causal recall inspection
- Phase 5: replay engine, step inspection, and offline snapshot diffing

For details, see:

- `docs/roadmap.md`
- `docs/testing.md`
- `docs/versioning.md`

## Repository Structure

```text
src/memfs_doctor/
  adapters/     framework-specific ingestion and capture
  cli/          command-line entry points
  core/         events, metrics, replay, snapshots, reporting
  reports/      terminal and JSON rendering helpers
  runtime/      runtime trace recording helpers
  storage/      SQLite event store
tests/          automated coverage
docs/           roadmap, testing notes, version history
examples/       sample traces and project assets
```

## Current State

This is a real product direction with an early but functional implementation. It is already useful for local session analysis and regression-oriented memory testing, especially in Letta-based workflows. The broader vision is larger than the current codebase, but the core loop of capture, measure, replay, and compare is now in place.
