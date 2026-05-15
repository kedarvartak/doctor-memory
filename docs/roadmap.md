# Roadmap

## Scope Of This Roadmap

This roadmap intentionally covers only the current execution focus:

1. Datadog for agent memory
2. Memory replay

It does not yet schedule auto-healing, benchmark publishing, visual graph exploration, or sleep-time optimization. Those should be layered on after observability and replay primitives are stable.

## Guiding Principles

- Build the core as a Python-first, framework-neutral engine.
- Make Letta the first-class initial adapter.
- Normalize framework data into a common event schema.
- Start CLI-first before investing in a full dashboard UI.
- Prioritize debuggability and correctness over breadth.

## Phase 0: Documentation And Architecture Baseline

### Objective

Define the product shape clearly enough that implementation can proceed without architecture drift.

### Deliverables

- product vision and scope doc
- phased roadmap
- change log discipline
- initial package structure proposal
- normalized event model draft

### Exit Criteria

- the team agrees on framework-neutral positioning
- Letta is confirmed as the first adapter target
- the first implementation boundary is limited to metrics and replay

## Phase 1: Core Event Model And Local Trace Storage

### Objective

Create the canonical memory event pipeline that every adapter will emit into.

### Deliverables

- Python package scaffold
- base adapter interface
- normalized event schema
- session model
- snapshot model
- local SQLite storage
- JSONL import/export for trace files

### Design Requirements

- events must be append-only
- snapshots must be reconstructible from events
- events must preserve original framework metadata
- storage should support replay queries efficiently

### Key Questions

- What is the minimum stable event schema?
- Which fields are required vs adapter-specific?
- Do we store full memory payloads or diffs first?

### Exit Criteria

- a synthetic session can be stored and replayed from local data
- a Letta adapter can emit at least basic write and retrieval events

## Phase 2: Letta Adapter MVP

### Objective

Integrate with Letta as the first real framework target and make trace capture practical.

### Deliverables

- `letta` adapter package
- event mapping from Letta memory activity to normalized schema
- agent/session discovery
- local capture workflow for test sessions
- CLI entry points for listing and inspecting Letta traces

### Design Requirements

- integration should remain external where possible
- avoid maintaining a fork of Letta
- adapter output must be portable into the shared analysis pipeline

### Key Questions

- Which Letta APIs and local artifacts expose the most useful memory signals?
- What level of instrumentation is possible without invasive runtime changes?
- How should agent and session identity be normalized?

### Exit Criteria

- a real Letta session can be captured into the local event store
- trace output includes writes, updates, retrievals, misses, and timing metadata where available

## Phase 3: Memory Metrics MVP

### Objective

Ship the first observability layer that makes agent memory measurable.

### Deliverables

- metric computation engine
- per-session health report
- CLI metrics command
- threshold configuration support
- regression-ready report serialization

### Initial Metrics

- retrieval latency
- memory tokens loaded
- context pressure score
- memory churn rate
- duplicate rate
- contradiction score
- stale recall rate
- empty retrieval rate

### Outputs

- terminal summary report
- JSON report artifact
- machine-readable health score payload

### Design Requirements

- metrics should run on stored traces, not only live sessions
- every metric should document its formula and known limitations
- reports should be comparable across runs

### Exit Criteria

- metrics run successfully on captured Letta traces
- at least one regression comparison can be generated between two sessions

## Phase 4: Retrieval Tracing And Explainability

### Objective

Explain why a memory was retrieved and what effect it had.

### Deliverables

- retrieval trace model
- causality links between query, retrieved memory, and subsequent use
- CLI retrieval inspection command
- report output for top problematic recalls

### What This Phase Should Answer

- why a retrieval happened
- what memories were selected
- whether those memories were useful or noisy
- which recalls increased token pressure most

### Design Requirements

- preserve ordering and causality in traces
- attach scoring metadata when the framework provides it
- support adapter-specific annotations without breaking the common schema

### Exit Criteria

- a developer can inspect a retrieval path for a specific session step
- noisy and stale recalls can be surfaced in a report

## Phase 5: Memory Replay MVP

### Objective

Make memory history replayable and debuggable session by session.

### Deliverables

- replay engine
- timeline traversal API
- before/after memory snapshot diffing
- step inspection command
- session replay CLI

### Core Replay Features

- list ordered memory events
- jump to any step in the session
- reconstruct memory state at a point in time
- diff memory state between two steps
- highlight first contradiction or duplication event

### Design Requirements

- replay should be deterministic from stored events
- diffs should be understandable in terminal output
- replay must work offline from exported trace files

### Exit Criteria

- a developer can replay a Letta session from stored data
- the system can identify the first event associated with a selected issue class

## Phase 6: Alerts, Regression Diffs, And CI Hooks

### Objective

Turn observability and replay into an engineering workflow, not just a local debugging tool.

### Deliverables

- configurable thresholds for memory health
- session-to-session regression diff reports
- non-zero exit codes for failing checks
- CI-friendly JSON output
- baseline report comparison workflow

### Example Checks

- contradiction score increased by more than threshold
- retrieval latency regressed beyond tolerance
- duplicate rate exceeded cap
- context pressure exceeded budget

### Exit Criteria

- a CI job can fail based on memory health regressions
- reports can be versioned and compared in a repeatable way

## Phase 7: Dashboard Foundation For Memory Observability

### Objective

Expose the data visually after the core engine is already useful in CLI and CI form.

### Deliverables

- local web dashboard or lightweight service
- session timeline view
- metric trend charts
- issue summary panels
- replay entry points

### Important Constraint

This phase should not turn into a frontend-first rewrite. The dashboard is a presentation layer over already-solid storage, analysis, and replay primitives.

### Exit Criteria

- dashboard views consume the same report and replay data produced by CLI workflows

## Immediate Build Order

The recommended order for the next implementation steps is:

1. Define package structure and normalized event schema.
2. Build local storage and trace persistence.
3. Implement the Letta adapter MVP.
4. Ship first-pass metrics.
5. Ship retrieval tracing.
6. Ship deterministic replay and diffs.

## What Counts As Version 0.1

Version `0.1` should mean:

- Letta session traces can be captured
- normalized events are stored locally
- basic memory health metrics are computed
- retrieval traces are inspectable
- session replay works from stored traces

At that point the project has a credible foundation as observability and replay infrastructure for persistent agent memory.
