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

## 2026-05-15 | v0.1.3-letta-local-import

Type: feature
Summary: Added real local Letta agent discovery and MemFS git-history import with test coverage and live verification.

Changes:
- Added Letta local state discovery for agents under `~/.letta/agents`.
- Added `ingest-letta-agent` and `letta-agents` CLI commands.
- Implemented git-history import from a Letta memory repo into normalized session events.
- Added synthetic fixture tests for local discovery and git-backed memory mutation import.
- Fixed a false-positive contradiction case by excluding markdown frontmatter metadata from semantic memory attributes.
- Verified the importer against the real local agent `agent-9edb3aaa-735a-4db6-b9e0-dee86bcc8998` present on this machine.

Reason:
- File-based JSONL ingestion was not enough for meaningful Letta validation.
- The project needed a bridge from real MemFS artifacts into the shared observability pipeline before deeper replay and retrieval analysis work.

Next:
- Add retrieval-aware capture beyond git history so reads, misses, and usefulness signals can be imported from real Letta activity.
- Improve session modeling so repeated live imports can be compared over time rather than only by current git head state.

## 2026-05-15 | v0.1.4-letta-session-capture

Type: feature
Summary: Added bounded start/finish session capture so real Letta activity can be ingested as a true session window instead of only full-history imports.

Changes:
- Added capture state storage in the project-local `.memfs_doctor/captures` directory.
- Added `start-letta-capture`, `finish-letta-capture`, and `letta-captures` CLI commands.
- Implemented incremental MemFS import bounded by the git head present at capture start.
- Added automated coverage proving that only commits created after capture start are included in the resulting session.
- Verified live start/list/finish capture behavior against the real local Letta agent on this machine without mutating the user's memory repo.

Reason:
- Criterion 1 required capturing a real Letta session into the local event store, not only reconstructing synthetic sessions from the full MemFS history.
- A bounded capture window is the safest practical bridge to true session traces with the local artifacts currently available.

Next:
- Capture retrievals, misses, and timing metadata from real Letta runtime artifacts so Phase 2 can satisfy the remaining trace-detail exit criteria.
- Improve automatic session naming and correlation once richer Letta session metadata becomes available.

## 2026-05-15 | v0.1.5-runtime-trace-merge

Type: feature
Summary: Added runtime-trace augmentation so bounded Letta session captures can include retrievals, misses, and timing metadata when available.

Changes:
- Added `--runtime-trace <jsonl>` support to `finish-letta-capture`.
- Implemented runtime trace filtering and merge into the bounded capture session id.
- Preserved retrieval metadata such as `latency_ms`, `tokens_loaded`, and `score` in merged events.
- Added automated coverage for merging retrieval and retrieval-miss events into a captured session.
- Verified a CLI-level synthetic workflow where a bounded capture stored retrieval and miss events and produced non-zero retrieval metrics.

Reason:
- Git-backed MemFS history alone cannot satisfy the Phase 2 trace-detail requirement around recalls, misses, and timing metadata.
- A merge path lets MemFS Doctor consume richer Letta runtime traces when those artifacts are available without changing the existing session-capture model.

Next:
- Identify or enable a real Letta runtime export path so retrieval and miss events come from actual Letta runs rather than synthetic JSONL fixtures.
- Add tighter correlation between runtime events and mutation events once conversation-level identifiers are exposed consistently.

## 2026-05-15 | v0.1.6-wrapped-runtime-recorder

Type: feature
Summary: Added a wrapped Letta terminal recorder that generates runtime JSONL traces automatically and can auto-finish bounded captures.

Changes:
- Added `memfs_doctor.runtime.letta_runtime` for transcript capture, turn parsing, retrieval/miss inference, and JSONL trace writing.
- Added the `record-letta-runtime` CLI command with optional `--auto-finish`.
- Implemented a default runtime trace output path under `.memfs_doctor/runtime/`.
- Added tests for transcript parsing and runtime trace writing.
- Verified an end-to-end wrapped fake Letta session where inferred retrieval and miss events were written and ingested into SQLite automatically.

Reason:
- The user needed a practical way to test Criterion 2 without hunting for a non-existent built-in Letta runtime trace export in the current local install.
- A wrapped terminal recorder is the fastest path to workflow-integrated runtime traces while staying compatible with the existing bounded session-capture model.

Next:
- Validate the wrapper against a real interactive Letta session in the user's environment.
- Improve inference quality and event correlation once more native Letta runtime signals are available.

## 2026-05-15 | v0.2.0-phase3-reporting

Type: feature
Summary: Implemented the Phase 3 reporting layer with health reports, threshold findings, and session-to-session regression comparison.

Changes:
- Added `memfs_doctor.core.reporting` with threshold rules, health reports, comparison reports, and JSON export helpers.
- Added `report` and `compare-sessions` CLI commands.
- Added rendered outputs for health reports and comparison reports.
- Added automated tests for threshold evaluation, report export, and regression comparison.
- Documented the manual Letta validation path for baseline health reports and session comparison.

Reason:
- Phase 3 requires turning raw metrics into durable observability outputs that can be compared across sessions.
- The project needed a first-class reporting layer before adding CI hooks or alert-style workflows.

Next:
- Add configurable threshold files rather than only built-in defaults.
- Add non-zero exit behavior for failing report thresholds and regression checks in the next workflow-oriented phase.

## 2026-05-15 | v0.3.0-phase4-retrieval-explainability

Type: feature
Summary: Implemented the first retrieval explainability layer with causal recall inspection and report-level problematic recall surfacing.

Changes:
- Added `memfs_doctor.core.retrievals` for retrieval-path analysis, causal write linkage, and token-pressure ranking.
- Added `inspect-retrieval` CLI command for session-level and step-level retrieval inspection.
- Extended health reports to include top problematic recalls.
- Added automated tests for retrieval causality and explainability output.
- Documented the manual validation path for retrieval inspection.

Reason:
- Phase 4 requires answering why a retrieval happened, what memory was selected, and whether a recall was stale or noisy.
- Developers needed a retrieval-specific inspection workflow beyond aggregate health metrics.

Next:
- Improve causality by attaching framework-native retrieval ranking metadata when available.
- Add richer noisy-recall heuristics that incorporate post-retrieval agent behavior, not only retrieval metadata.

## 2026-05-16 | v0.4.0-phase5-memory-replay

Type: feature
Summary: Completed the first replay-oriented debugging layer with step inspection, richer snapshot diffs, and offline replay from trace files.

Changes:
- Expanded `memfs_doctor.core.replay` with structured replay timeline entries, step inspection, richer diff output, and final snapshot summary fields.
- Added `inspect-step` CLI command for step-by-step memory state inspection.
- Extended `replay` and `diff` to work directly from trace files through `--trace-path`, not only from stored sessions.
- Updated replay renderers and automated tests to cover timeline flags, snapshot deltas, and offline replay parity.
- Added a dedicated Phase 5 manual validation scenario to `docs/testing.md`.

Reason:
- Phase 5 requires deterministic session replay, timeline traversal, step inspection, and understandable before/after memory diffs.
- Developers needed an offline replay path that does not depend on the SQLite event store.

Next:
- Add more compact terminal rendering for large snapshots and diffs.
- Introduce exportable replay artifacts if teams want to persist replay views separately from raw events.
