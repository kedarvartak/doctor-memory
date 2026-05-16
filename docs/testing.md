# Testing Strategy

This project should not move from one implementation step to the next without passing both:

1. automated verification
2. manual validation for the affected workflow

This rule applies to every feature, refactor, adapter expansion, and replay/metrics change.

## Release Gate Policy

For every implementation increment:

- write or update automated tests first when practical, or in the same change at minimum
- run the relevant automated test suite before declaring the step complete
- document the exact commands used for verification
- define a manual validation checklist for real behavior that unit tests cannot prove
- do not move to the next roadmap item until the current gate passes

## Preferred Short Commands

The full command names remain supported, but the preferred UX is now the short command layer.

Common shortcuts:

- `memops dash`
  Start the local dashboard
- `memops agents`
  List local Letta agents
- `memops captures`
  List pending bounded captures
- `memops capture`
  Start a bounded Letta capture
- `memops record`
  Wrap an existing capture around a Letta terminal run
- `memops finish`
  Finish a bounded capture into the local store
- `memops chat`
  Start capture, run Letta, and auto-finish in one command
- `memops runs`
  List stored sessions
- `memops health`
  Generate a session health report
- `memops compare`
  Compare two sessions
- `memops regress`
  Run regression gate logic
- `memops bench`
  Run an automated baseline-vs-candidate regression check from two trace files
- `memops retrieval`
  Inspect retrieval quality and causality
- `memops timeline`
  Replay a session timeline
- `memops step`
  Inspect one replay step
- `memops shots`
  Inspect per-turn health snapshots

## Automated Test Gate

### Current Baseline Commands

Run these after every meaningful implementation change unless a narrower command is clearly sufficient:

```bash
uv run python3 -m unittest discover -s tests
memops --help
memops agents
memops captures
```

### Current End-To-End CLI Check

This validates the local event store, ingestion path, metrics, and replay path:

```bash
memops --db /tmp/memops-test.db init-db
memops --db /tmp/memops-test.db ingest examples/letta_session.jsonl --framework letta
memops --db /tmp/memops-test.db session --session session-001
memops --db /tmp/memops-test.db stats --session session-001 --json
memops --db /tmp/memops-test.db timeline --session session-001
memops --db /tmp/memops-test.db diff --session session-001 --before-step 2 --after-step 6
```

### Expected Current Assertions

For the sample Letta trace:

- unit tests pass
- ingest reports `9` events
- replay reports first duplicate event at step `4`
- replay reports first contradiction event at step `6`
- metrics returns non-zero duplicate and contradiction scores

For the local Letta git-import path:

- local Letta agents are listed when `~/.letta/agents` exists
- `ingest-letta-agent` creates a synthetic session from MemFS git history
- the imported session appears in `sessions`
- imported metrics do not report false contradiction scores from markdown frontmatter alone

For the bounded Letta session capture path:

- `start-letta-capture` creates a pending capture marker in the local project workspace
- `letta-captures` lists the pending capture id
- `finish-letta-capture` ingests a bounded session into the local store
- the resulting session id uses the `letta-session:<agent>:<conversation>:...` form
- the pending capture disappears after successful finish

For the runtime-trace augmentation path:

- `finish-letta-capture --runtime-trace <jsonl>` merges retrieval and miss events into the bounded session
- retrieval events preserve `latency_ms`, `tokens_loaded`, and `score` when present
- retrieval miss events contribute to `empty_retrieval_rate`
- resulting metrics reflect retrieval timing and token pressure from the runtime trace

For the wrapped terminal runtime recorder:

- `record-letta-runtime` generates the runtime JSONL trace automatically
- `record-letta-runtime --auto-finish` also finishes the bounded session capture into SQLite
- transcript-derived retrieval events are marked as inferred in metadata
- miss detection comes from response-content heuristics and should be validated manually against the visible Letta exchange

For the Phase 3 reporting path:

- `report --session <id>` returns a health report with thresholds and findings
- `compare-sessions --baseline <id> --candidate <id>` returns deltas and regression counts
- `benchmark --baseline-trace <path> --candidate-trace <path>` runs the same regression logic directly from two trace files
- report output can be exported as JSON artifacts
- comparison output should flag worsened metrics such as higher duplicate rate or higher empty retrieval rate

For the Phase 4 retrieval explainability path:

- `inspect-retrieval --session <id>` returns retrieval traces with cause linkage
- `inspect-retrieval --session <id> --step <n>` returns the specific retrieval path for one timeline step
- retrieval inspection surfaces likely noisy recalls and top token-pressure recalls
- `report --session <id>` includes top problematic recalls when present

## Manual Test Policy

Automated tests are necessary but not sufficient. For memory systems, manual tests should confirm that the metrics and replay outputs feel directionally correct against real agent behavior.

Every implementation phase should add or update a manual test checklist with:

- setup prerequisites
- exact test prompts or session flows
- expected behavior in Letta
- expected MemOps output characteristics
- pass/fail notes

## Manual Test Matrix

## Phase 1 Manual Tests: Local Trace And Replay Foundation

These tests validate the current baseline without requiring live Letta integration.

### Manual Test 1: Sample Trace Sanity

Goal:
- verify that the provided sample trace produces stable and understandable metrics and replay output

Steps:
1. initialize a clean local database
2. ingest `examples/letta_session.jsonl`
3. run `inspect`, `metrics`, `replay`, and `diff`

Expected result:
- one session appears
- event count is `9`
- duplicate rate is greater than `0`
- contradiction score is greater than `0`
- replay timeline is ordered and readable
- diff between steps `2` and `6` shows new memory creation

### Manual Test 2: Broken Trace Rejection

Goal:
- verify that invalid trace data fails loudly rather than entering the store silently

Steps:
1. create a malformed JSONL file with one invalid line
2. run the `ingest` command against it

Expected result:
- ingest exits with an error
- the error references the failing line number
- no partial silent success message is shown

## Phase 2 Manual Tests: Letta Session Validation

These should be run once Letta is accessible in the environment.

### Preconditions

- `letta` CLI is installed and available on `PATH`, or the Letta Python package is available in the same environment
- you can create and run a persistent agent session
- you can export or otherwise capture the resulting memory-relevant session events

### Manual Test 3: Stable Session Baseline

Goal:
- establish what healthy memory metrics look like over a normal session

Commands:

```bash
memops agents
memops --db /tmp/memops-manual.db init-db
memops --db /tmp/memops-manual.db ingest-letta-agent --agent <agent-id>
memops --db /tmp/memops-manual.db runs
memops --db /tmp/memops-manual.db stats --session <session-id> --json
memops --db /tmp/memops-manual.db timeline --session <session-id>
```

Suggested Letta session flow:
1. create or open a test agent
2. tell the agent three stable facts:
   - user name is `Asha`
   - city is `Pune`
   - favorite editor is `VS Code`
3. ask three recall questions about those facts
4. end the session
5. export or capture the session trace
6. ingest the trace into MemOps
7. run `metrics` and `replay`

Expected MemOps result:
- duplicate rate should be low, ideally `0`
- contradiction score should be `0`
- empty retrieval rate should be low
- replay should show a clean sequence of writes followed by recalls
- average retrieval latency should be consistent across repeated runs in the same environment

Pass condition:
- results are directionally healthy and stable across two or three repeated baseline sessions

### Manual Test 4: Duplicate Memory Session

Goal:
- confirm that duplicate writes are visible in metrics and replay

Commands:

```bash
memops --db /tmp/memops-duplicate.db init-db
memops --db /tmp/memops-duplicate.db ingest-letta-agent --agent <agent-id>
memops --db /tmp/memops-duplicate.db runs
memops --db /tmp/memops-duplicate.db stats --session <session-id> --json
memops --db /tmp/memops-duplicate.db timeline --session <session-id>
```

Suggested Letta session flow:
1. create or open a test agent
2. store the same fact in slightly repeated form multiple times
   - `User likes green tea`
   - `User likes green tea`
   - `The user prefers green tea`
3. ask the agent to recall the preference
4. export or capture the trace
5. ingest the trace
6. run `metrics` and `replay`

Expected MemOps result:
- duplicate rate increases above the stable baseline
- replay highlights the first duplicate-introducing event
- event timeline makes it obvious which write caused the duplication

Pass condition:
- duplicate-oriented metrics and replay both point to the same general issue

### Manual Test 5: Contradiction Session

Goal:
- confirm that conflicting facts surface as contradiction risk

Commands:

```bash
memops --db /tmp/memops-contradiction.db init-db
memops --db /tmp/memops-contradiction.db ingest-letta-agent --agent <agent-id>
memops --db /tmp/memops-contradiction.db stats --session <session-id> --json
memops --db /tmp/memops-contradiction.db timeline --session <session-id>
```

Suggested Letta session flow:
1. create or open a test agent
2. store one fact:
   - `User city is Pune`
3. later in the same session store a conflicting fact:
   - `User city is Mumbai`
4. ask the agent where the user lives
5. export or capture the trace
6. ingest the trace
7. run `metrics` and `replay`

Expected MemOps result:
- contradiction score increases above baseline
- replay points to the first conflicting write event
- retrieval review should show the affected city-related memory path

Pass condition:
- contradiction reporting is directionally correct and the replay story matches the session behavior

### Manual Test 6: Retrieval Miss Session

Goal:
- confirm that missing memories appear as retrieval misses rather than silent success

Suggested Letta session flow:
1. create or open a test agent
2. avoid storing a fact about favorite food
3. ask for favorite food
4. export or capture the trace
5. ingest the trace
6. run `metrics`

Expected MemOps result:
- empty retrieval rate or retrieval miss indicators increase
- no false successful recall should appear for that question

Pass condition:
- the report reflects the retrieval miss in a visible way

### Manual Test 7: Local Letta Discovery And Import

Goal:
- confirm that MemOps can discover a real local Letta agent and import its MemFS git history without hand-built trace files

Commands:

```bash
memops agents
memops --db /tmp/memops-live.db init-db
memops --db /tmp/memops-live.db ingest-letta-agent --agent <agent-id>
memops --db /tmp/memops-live.db runs
memops --db /tmp/memops-live.db stats --session <session-id> --json
memops --db /tmp/memops-live.db timeline --session <session-id>
```

Expected result:
- at least one real local agent is listed when Letta has bootstrapped memory locally
- import succeeds without requiring manual JSONL authoring
- `sessions` shows a synthetic `letta-git:<agent-id>:<head>` session id
- metrics output is stable and does not show false contradictions from frontmatter-only differences
- replay shows a deterministic timeline of git-derived memory mutations

Pass condition:
- a real local MemFS repo can be discovered and imported end to end

### Manual Test 8: Bounded Real Letta Session Capture

Goal:
- confirm that MemOps captures one real Letta session as its own bounded session trace instead of importing all historical MemFS state

Commands:

```bash
memops agents
memops capture --agent <agent-id>
# run a real Letta session here that changes memory
memops captures
memops --db .memops/session.db finish --capture-id <capture-id>
memops --db .memops/session.db runs
memops --db .memops/session.db session --session <session-id>
memops --db .memops/session.db timeline --session <session-id>
```

Suggested Letta session flow:
1. start a capture for the target agent
2. open or continue one conversation in Letta
3. make one memory-affecting interaction such as teaching a durable fact
4. optionally make one follow-up interaction that updates the same fact
5. finish the capture

Expected result:
- the resulting session is separate from full-history imports
- only commits created during the capture window are included
- `sessions` shows a `letta-session:...` session id
- `inspect` and `replay` show only the mutations that happened after capture start
- if no memory commits occurred during the window, the session still exists with just start/end events

Pass condition:
- a real Letta conversation window can be bracketed and stored as one bounded session trace in the local event store

### Manual Test 9: Runtime Trace Augmented Session

Goal:
- confirm that a bounded Letta session can include retrievals, misses, and timing metadata when a runtime trace is available

Commands:

```bash
memops capture --agent <agent-id>
# run a real Letta session here that causes at least one recall and one miss
memops --db .memops/session.db finish \
  --capture-id <capture-id> \
  --runtime-trace <path-to-runtime-trace.jsonl>
memops --db .memops/session.db session --session <session-id>
memops --db .memops/session.db stats --session <session-id> --json
memops --db .memops/session.db timeline --session <session-id>
```

Suggested runtime trace contents:
- one `memory_retrieved` event
- one `memory_retrieval_miss` event
- `latency_ms` on both when available
- `tokens_loaded` on retrieval when available
- the real Letta `agent_id`
- timestamps inside the capture window

Expected result:
- `inspect` shows retrieval and miss event kinds in the session
- `metrics` shows non-zero `retrieval_count`
- `metrics` shows non-zero `retrieval_latency_ms_avg`
- `metrics` shows non-zero `empty_retrieval_rate`
- `metrics` reflects `memory_tokens_loaded_total` when provided
- `replay` includes retrieval and miss entries in the session timeline

Pass condition:
- bounded session capture plus runtime trace produces a single stored session containing both mutation and retrieval-side events

### Manual Test 10: Wrapped Letta Runtime Recorder

Goal:
- confirm that MemOps can generate the runtime trace itself while you use terminal Letta normally

Commands:

```bash
memops --db .memops/session.db chat -- letta
memops --db .memops/session.db session --session <session-id>
memops --db .memops/session.db stats --session <session-id> --json
memops --db .memops/session.db timeline --session <session-id>
```

Suggested Letta interaction:
1. ask one recall-style question for a fact the agent should know
2. ask one question for a fact the agent does not know
3. optionally issue one remember/update command in the same session
4. exit Letta cleanly

Expected result:
- a runtime trace file is written under `.memops/runtime/`
- the stored session includes `memory_retrieved` and `memory_retrieval_miss`
- `metrics` shows non-zero `retrieval_count`
- `metrics` shows non-zero `empty_retrieval_rate`
- `replay` includes the inferred retrieval-side events in session order

Pass condition:
- you can test Criterion 2 without manually authoring a runtime JSONL file

Important note:
- retrieval and miss events produced by the wrapper are inferred from the visible terminal transcript
- treat them as workflow-grounded instrumentation, not native Letta internal event exports

### Manual Test 11: Phase 3 Healthy Baseline Report

Goal:
- generate a health report from a relatively clean Letta session and verify the report/finding structure

Suggested Letta flow:
1. start a fresh bounded capture
2. ask one known fact question
3. avoid contradictory or duplicate memory writes
4. finish the session through `record-letta-runtime --auto-finish`
5. run `report --session <session-id> --json`

Commands:

```bash
memops --db .memops/session.db health \
  --session <session-id> \
  --json
```

Expected result:
- report JSON contains `status`, `metrics`, and `findings`
- `retrieval_count` is non-zero if you asked a known fact question
- findings are fewer and less severe than in intentionally messy sessions

Pass condition:
- a health report is generated successfully from a real Letta session

### Manual Test 12: Phase 3 Regression Comparison

Goal:
- compare two real Letta sessions and verify the regression output flags worse memory behavior

Suggested setup:
1. create a baseline session with one clean recall and no duplicate updates
2. create a candidate session with at least one miss and one noisy or repeated memory update
3. finish both sessions through the runtime wrapper
4. compare them

Commands:

```bash
memops --db .memops/session.db compare \
  --baseline <baseline-session-id> \
  --candidate <candidate-session-id> \
  --json
```

Expected result:
- output contains `deltas`, `regressions`, and `regression_count`
- worsened metrics such as `empty_retrieval_rate`, `duplicate_rate`, or `memory_churn_rate` appear in regressions

Pass condition:
- the comparison surfaces directionally correct regressions between two real Letta sessions

### Manual Test 13: Phase 4 Retrieval Path Inspection

Goal:
- inspect why a retrieval happened, which memory was selected, and whether the recall looks useful or noisy

Suggested setup:
1. create a session with at least two stored facts and two recall questions
2. include one healthy recall and one stale or low-confidence recall if possible
3. finish the session through the runtime wrapper or merge a runtime trace into the bounded capture
4. run retrieval inspection against the stored session

Commands:

```bash
memops --db .memops/session.db retrieval \
  --session <session-id> \
  --json

memops --db .memops/session.db retrieval \
  --session <session-id> \
  --step <retrieval-step>
```

Expected result:
- each retrieval trace contains the query, selected memory id, and retrieval timing fields when available
- retrieval traces link back to the most recent causal memory write for the retrieved memory id
- stale recalls appear under top problematic recalls
- token-heavy recalls appear under top token pressure recalls

Pass condition:
- a developer can explain a specific recall using the inspection output without manually reconstructing the full timeline

### Manual Test 14: Phase 5 Session Replay And Step Diff

Goal:
- replay a session deterministically, inspect a specific step, and diff memory state between two steps

Suggested setup:
1. use an existing stored Letta session with at least one create and one update event
2. or ingest `examples/letta_session.jsonl` into a scratch database
3. run replay for the whole session
4. inspect one middle step where memory changed
5. diff an earlier step against a later step
6. repeat the replay directly from the trace file to confirm offline behavior

Commands:

```bash
memops timeline \
  --session <session-id>

memops step \
  --session <session-id> \
  --step <step-number> \
  --json

memops diff \
  --session <session-id> \
  --before-step <earlier-step> \
  --after-step <later-step> \
  --json

memops timeline \
  --trace-path examples/letta_session.jsonl \
  --json
```

Expected result:
- replay output includes ordered steps, first duplicate/contradiction markers, and final memory count
- step inspection includes the event payload, snapshot at that point, and delta from the previous step
- diff output includes `created`, `updated`, `deleted`, and per-memory `details`
- offline replay from `--trace-path` produces the same timeline shape as the stored session replay

Pass condition:
- a developer can jump to a step, see memory state at that point, and explain what changed without manually replaying the full session

### Manual Test 15: Phase 6 Health Checks And Regression Gates

Goal:
- use thresholded health checks and regression checks as a repeatable fail/pass workflow

Suggested setup:
1. ingest a stored trace into a scratch database
2. run a session health check with default thresholds
3. run the same report with a custom threshold file
4. prepare a baseline and candidate pair, then run a regression check
5. confirm non-zero exit codes are returned on failure

Commands:

```bash
memops --db /tmp/memops-phase6.db init-db

memops --db /tmp/memops-phase6.db ingest \
  examples/letta_session.jsonl \
  --framework letta

memops --db /tmp/memops-phase6.db gate \
  --session session-001 \
  --json

memops --db /tmp/memops-phase6.db health \
  --session session-001 \
  --thresholds examples/phase6_thresholds.json \
  --json

memops --db .memops/session.db regress \
  --baseline <baseline-session-id> \
  --candidate <candidate-session-id> \
  --regression-thresholds examples/phase6_thresholds.json \
  --json
```

Expected result:
- `check-session` returns JSON with `status`, `exit_code`, `summary`, and full report payload
- exit code is non-zero when threshold findings breach the configured fail policy
- `report --thresholds ...` reflects the custom threshold file instead of only built-in defaults
- `check-regression` returns JSON with regression findings and a non-zero exit code when candidate deltas exceed tolerance

Pass condition:
- a CI job can fail deterministically from session health or regression findings without custom wrapper logic

### Manual Test 15B: Automated Baseline And Candidate Benchmark

Goal:
- verify that a baseline and candidate trace can be compared automatically without first ingesting them into SQLite

Suggested setup:
1. create or export one baseline trace that represents stable memory behavior
2. create or export one candidate trace that includes a worse retrieval or noisier memory mutation pattern
3. run the benchmark command against both trace files
4. confirm the candidate fails when regression thresholds are breached

Commands:

```bash
memops bench \
  --baseline-trace <baseline-trace.jsonl> \
  --candidate-trace <candidate-trace.jsonl> \
  --regression-thresholds examples/phase6_thresholds.json \
  --json
```

Expected result:
- output contains `baseline_report`, `candidate_report`, `comparison`, and `check`
- `comparison.regressions` lists all directionally worse metrics
- `comparison.regression_findings` lists only metrics that breach configured regression policy
- command exits non-zero when the candidate degrades beyond tolerance

Pass condition:
- the same trace pair can be re-run repeatedly and produce stable pass/fail regression judgments

## Manual Test 16: Dashboard Foundation

Goal:
- verify that the local dashboard consumes the same stored data as the CLI
- verify that wrapped Letta sessions emit per-turn health snapshots into the dashboard while the session is still running

Commands:

```bash
memops --db /tmp/memops-dashboard.db capture --agent <agent-id>

memops --db /tmp/memops-dashboard.db dash

memops --db /tmp/memops-dashboard.db chat -- letta
```

Manual validation:
- open `http://127.0.0.1:8765`
- confirm the current session appears in the left session list
- send multiple Letta prompts that create writes and at least one retrieval
- confirm the per-turn health table grows while the session is still running
- confirm the trend charts move as turns accumulate
- after the session exits, confirm replay and stored report data are visible for the same session

Pass condition:
- dashboard views consume the same underlying session data produced by the CLI capture and reporting workflow

## Manual Test 17: Agent Observability Dashboard

Goal:
- verify that the dashboard behaves like an observability surface, not only a static report viewer
- verify that degradation and root-cause hints appear from the same stored session data as the CLI

Commands:

```bash
memops --db .memops/session.db dash

memops --db .memops/session.db capture --agent <agent-id>

memops --db .memops/session.db chat -- letta
```

Manual validation:
- open `http://127.0.0.1:8765`
- confirm the selected session shows a health timeline rather than only a raw table
- create a session with at least one retrieval and one memory write
- introduce a degrading turn, such as a correction, conflicting fact, or noisy rewrite
- confirm the incident feed surfaces the degraded turn or threshold breach
- confirm the root-cause panel identifies the first degraded turn or other first-known issue markers
- confirm the event stream reflects the same session progression visible through CLI replay and retrieval inspection

Pass condition:
- a developer can use the dashboard to see when the session degraded and what likely caused it, without leaving the UI first

## Manual Test Notes Template

Use this template after each manual run:

```text
Date:
Phase:
Scenario:
Trace source:

Observed Letta behavior:
- ...

Observed MemOps output:
- ...

Pass/Fail:
- ...

Follow-up:
- ...
```

## What Must Be True Before We Move Ahead

Before starting the next implementation item:

- automated tests for the current change are written or updated
- automated test commands pass locally
- at least one relevant manual test is documented
- if the change affects Letta behavior, the matching Letta manual scenario is defined
- the final implementation note includes both automated and manual verification status
