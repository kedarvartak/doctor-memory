# Versioning Log

This file records every meaningful project change from the beginning of the repository. It should function as a durable project journal, not just a release summary.

## Rules

- Log every meaningful documentation, architecture, feature, refactor, adapter, and testing change.
- Use chronological entries with explicit dates.
- Keep entries short but concrete.
- Record intent, not only file names.
- When implementation begins, log both shipped work and major design pivots.

## Entry Format

Use this structure for each entry:

```text
## YYYY-MM-DD | version-tag

Type: docs | architecture | feature | refactor | test | fix | chore
Summary: one-line summary

Changes:
- concrete change
- concrete change

Reason:
- why this change was made

Next:
- immediate follow-up
```

## Log

## 2026-05-15 | v0.1.0-docs-foundation

Type: docs
Summary: Established the initial documentation base for MemFS Doctor as framework-neutral memory observability and replay infrastructure.

Changes:
- Created `docs/idea.md` to define product positioning, core thesis, architecture direction, event model direction, and Letta-first but framework-neutral strategy.
- Created `docs/roadmap.md` with scoped phases focused only on memory observability and memory replay.
- Defined the initial implementation direction as Python-first, CLI-first, adapter-based, and local-storage-backed.
- Documented the first integration target as Letta while preserving plug-and-play support for future frameworks.

Reason:
- The project needed a clear product definition before implementation so architecture does not drift into a one-off Letta utility.
- The current milestone is strategy and structure, not feature sprawl.

Next:
- Scaffold the Python package layout.
- Draft the normalized memory event schema.
- Begin Letta adapter discovery and capture strategy.

## 2026-05-15 | v0.1.1-phase1-foundation

Type: architecture
Summary: Implemented the first working Python foundation for normalized memory traces, local storage, metrics, and replay.

Changes:
- Added Python packaging with a `src/` layout and a CLI entry surface for `init-db`, `ingest`, `sessions`, `inspect`, `metrics`, `replay`, and `diff`.
- Implemented normalized event and session models in `memfs_doctor.core.events`.
- Implemented snapshot reconstruction and memory-state diffs in `memfs_doctor.core.snapshots`.
- Implemented first-pass memory health metrics in `memfs_doctor.core.metrics`, including duplicate rate, contradiction score, stale recall rate, retrieval latency, context pressure, and churn.
- Implemented deterministic session replay helpers in `memfs_doctor.core.replay`.
- Implemented an SQLite-backed append-only event store in `memfs_doctor.storage.sqlite`.
- Added a Letta trace adapter that ingests JSONL exports into the normalized schema.
- Added a sample Letta session trace and unit tests covering ingestion, metrics, replay, and SQLite round-trip behavior.

Reason:
- Phase 1 required a stable local execution base before deeper Letta instrumentation or replay explainability work could begin.
- The project needed a framework-neutral core so Letta support remains an adapter, not the entire architecture.

Next:
- Expand the Letta adapter beyond file import into real session discovery and trace capture.
- Add richer retrieval tracing so replay can explain why recalls happened and whether they were useful.
- Introduce report export and regression comparison support for session-to-session observability workflows.

## 2026-05-15 | v0.1.2-testing-gate

Type: test
Summary: Added explicit automated and manual test gate documentation so implementation cannot advance without verification.

Changes:
- Created `docs/testing.md` with the project-wide verification policy, baseline automated commands, and a manual Letta validation matrix.
- Added roadmap language making tests a formal phase gate rather than an optional follow-up task.
- Updated `README.md` to point contributors to the testing workflow.
- Defined concrete manual Letta scenarios for baseline, duplicate memory, contradiction, and retrieval miss behavior.

Reason:
- The project needs a repeatable engineering workflow where every implementation step proves correctness before the next phase starts.
- Memory systems need both synthetic automated tests and real-session manual checks to validate that metrics and replay outputs are directionally trustworthy.

Next:
- Keep `docs/testing.md` in sync with each new feature and adapter capability.
- Add feature-specific automated tests as retrieval tracing and regression reporting are implemented.
