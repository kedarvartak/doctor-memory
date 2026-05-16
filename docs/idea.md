# MemOps

## Positioning

MemOps is a plug-and-play observability, diagnostics, and reliability layer for persistent AI memory systems.

It should not be positioned as a Letta-specific utility. Letta is the first high-quality integration target because it already exposes the right class of stateful agent behavior, but the product itself should remain framework-neutral. The long-term category is closer to "Datadog for agent memory" and "replay debugger for memory mutations" than "memory cleanup script."

The initial implementation should be in Python so the project can ship quickly as:

- a local CLI for developers
- a Python SDK for adapters
- an analysis engine for offline and live traces
- a backend service for future dashboards and alerts

## Core Thesis

Persistent agents fail silently when memory quality degrades. Existing frameworks expose memory storage and retrieval, but they generally do not provide:

- measurable reliability signals
- replayable memory mutation history
- root-cause analysis for bad recalls
- regression tracking across sessions
- framework-neutral memory diagnostics

MemOps exists to make agent memory observable, debuggable, and eventually self-healing.

## Initial Scope

The current focus is intentionally narrow:

1. Datadog for agent memory
2. Memory replay

These two areas create the core platform primitives that later features will build on.

## Problem Statement

Long-lived agents accumulate memory over time, but developers currently struggle to answer basic operational questions:

- Why did the agent recall this memory?
- When did a contradiction first enter the store?
- Is memory quality improving or degrading over time?
- Which sessions caused memory bloat?
- How much latency and token pressure is memory retrieval adding?
- Which framework integration is more stable under long-horizon use?

Without instrumentation and replay, these questions are mostly guesswork.

## Product Goals

### 1. Make memory measurable

Treat memory as a first-class production subsystem with metrics, traces, and health indicators.

### 2. Make memory replayable

Allow developers to inspect memory mutations and retrieval decisions step by step, similar to replay debugging or distributed tracing.

### 3. Stay framework-agnostic

Define a common internal memory event model so the same analysis engine can operate across Letta and future adapters.

### 4. Be operationally useful

The project should help teams catch regressions, explain failures, and reduce time spent debugging persistent-agent behavior.

## Non-Goals For The First Milestone

The following ideas are important, but they should not be part of the first execution phase:

- autonomous memory repair
- visual graph-heavy UI
- public benchmark publishing
- sleep-time optimization
- deep framework-specific forks

These depend on having a solid event model, metric model, and replay pipeline first.

## Product Shape

The project should evolve as four connected layers.

### 1. Adapter Layer

Adapters translate framework-specific memory events into a normalized internal schema.

Initial target:

- Letta adapter

Planned next targets:

- LangGraph
- OpenAI memory-compatible workflows
- Mem0
- Zep

### 2. Event And Snapshot Layer

This layer stores the canonical record of what happened to memory over time.

Core objects:

- memory item
- mutation event
- retrieval event
- session
- snapshot
- trace
- health report

### 3. Analysis Layer

This layer computes operational signals and diagnostics.

Examples:

- contradiction detection
- duplicate detection
- freshness decay scoring
- retrieval latency analysis
- token pressure analysis
- churn scoring
- recall usefulness scoring

### 4. Developer Experience Layer

This is how developers interact with the system.

Forms:

- CLI commands
- terminal summaries
- structured JSON output
- future web dashboard
- future alerting and CI integration

## Core Capabilities

## A. Datadog For Agent Memory

This capability turns memory into an observable subsystem.

### What it should provide

- memory health metrics
- session timelines
- anomaly detection
- regressions over time
- per-agent and per-framework comparisons
- alerts for reliability issues

### Candidate metrics

#### Structural quality

- `duplicate_rate`: percentage of near-duplicate memory entries
- `contradiction_score`: likelihood that memory items conflict semantically
- `orphan_memory_count`: items never recalled or referenced
- `memory_churn_rate`: rate of edits, rewrites, and deletes

#### Relevance and utility

- `recall_precision`: fraction of retrieved memories that were actually used
- `recall_waste_rate`: retrieved but ignored memories
- `freshness_decay`: age-weighted usefulness drop
- `stale_recall_rate`: frequency of old or superseded memories being retrieved

#### Cost and performance

- `retrieval_latency_ms`
- `memory_tokens_loaded`
- `context_pressure_score`
- `summary_compaction_ratio`
- `storage_growth_rate`

#### Reliability

- `hallucinated_memory_score`
- `failed_retrieval_count`
- `empty_retrieval_rate`
- `session_corruption_risk`

### Datadog-style outputs

- per-session memory health report
- rolling trend graphs
- threshold alerts
- regression diff between runs
- agent memory scorecard

## B. Memory Replay

This capability makes memory behavior inspectable.

### What it should provide

- replay of a session from start to finish
- event-by-event memory mutation inspection
- retrieval trace explanation
- before/after snapshot diffs
- root-cause isolation for corruption or bloat

### Replay questions it should answer

- Which event introduced a contradiction?
- Which write caused duplication?
- Why was a specific memory recalled?
- Which retrieval chain expanded context size?
- When did memory begin diverging from user intent?

### Replay primitives

- session timeline
- mutation log
- retrieval log
- memory snapshots
- diff viewer
- causality links between writes and recalls

### Replay modes

- offline replay from stored traces
- near-real-time replay after session completion
- deterministic replay for regression debugging

## Architecture Direction

The codebase should be structured around a normalized memory event contract rather than around any single framework.

Suggested Python package direction:

```text
memfs_doctor/
  adapters/
    base.py
    letta/
  core/
    events.py
    snapshots.py
    replay.py
    metrics.py
    scoring.py
  storage/
    sqlite.py
    files.py
  cli/
    main.py
  reports/
    health.py
    replay.py
  schemas/
    events.py
    reports.py
```

## Event Model Direction

Everything should normalize into a small number of event types.

Suggested event classes:

- `MemoryCreated`
- `MemoryUpdated`
- `MemoryDeleted`
- `MemoryRetrieved`
- `MemoryRetrievalMiss`
- `SummaryGenerated`
- `SessionStarted`
- `SessionEnded`
- `CompactionRun`

Each event should capture:

- framework
- agent id
- session id
- timestamp
- source component
- memory ids involved
- input query or trigger
- payload before and after
- token and latency metadata
- confidence or score metadata where available

## Storage Direction

For the first implementation, prefer a simple local-first setup:

- SQLite for normalized events and snapshots
- JSONL export/import for trace portability
- optional file-based reports

This keeps the project easy to run locally while preserving a clean path to later hosted infrastructure.

## Letta-First Strategy

Letta should be the first adapter, not the entire product definition.

Why Letta first:

- strong alignment with persistent memory workflows
- good demo value
- meaningful long-horizon state behavior
- fits the replay and observability thesis well

How to approach it:

- observe Letta memory writes and retrievals externally when possible
- avoid deep forks of the core runtime
- normalize Letta events into the shared schema
- keep the adapter boundary explicit so other frameworks can plug in later

## Developer Experience Direction

The first UX should be CLI-first.

Potential commands:

```bash
memops session --framework letta --agent <id>
memops stats --session <id>
memops timeline --session <id>
memops diff --session <id> --step 14 --step 28
memops export --session <id> --format jsonl
```

Outputs should be both human-readable and machine-consumable.

## Success Criteria For The First Version

The first meaningful version should let a developer do all of the following against a Letta-backed agent:

- capture memory-related events for a session
- compute core health metrics
- inspect retrieval traces
- replay a session timeline
- diff memory state between two moments
- identify at least basic contradictions and duplication patterns

If those capabilities work reliably, the project has a real platform foundation.
