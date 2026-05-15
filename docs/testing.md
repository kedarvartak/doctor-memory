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

## Automated Test Gate

### Current Baseline Commands

Run these after every meaningful implementation change unless a narrower command is clearly sufficient:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m memfs_doctor.cli.main --help
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-captures
```

### Current End-To-End CLI Check

This validates the local event store, ingestion path, metrics, and replay path:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db ingest examples/letta_session.jsonl --framework letta
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db inspect --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db metrics --session session-001 --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db replay --session session-001
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-test.db diff --session session-001 --before-step 2 --after-step 6
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
- expected MemFS Doctor output characteristics
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-manual.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-manual.db ingest-letta-agent --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-manual.db sessions
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-manual.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-manual.db replay --session <session-id>
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
6. ingest the trace into MemFS Doctor
7. run `metrics` and `replay`

Expected MemFS Doctor result:
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-duplicate.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-duplicate.db ingest-letta-agent --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-duplicate.db sessions
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-duplicate.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-duplicate.db replay --session <session-id>
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

Expected MemFS Doctor result:
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-contradiction.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-contradiction.db ingest-letta-agent --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-contradiction.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-contradiction.db replay --session <session-id>
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

Expected MemFS Doctor result:
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

Expected MemFS Doctor result:
- empty retrieval rate or retrieval miss indicators increase
- no false successful recall should appear for that question

Pass condition:
- the report reflects the retrieval miss in a visible way

### Manual Test 7: Local Letta Discovery And Import

Goal:
- confirm that MemFS Doctor can discover a real local Letta agent and import its MemFS git history without hand-built trace files

Commands:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-live.db init-db
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-live.db ingest-letta-agent --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-live.db sessions
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-live.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-live.db replay --session <session-id>
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
- confirm that MemFS Doctor captures one real Letta session as its own bounded session trace instead of importing all historical MemFS state

Commands:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-agents
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
# run a real Letta session here that changes memory
PYTHONPATH=src python3 -m memfs_doctor.cli.main letta-captures
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture --capture-id <capture-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db sessions
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect --session <session-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db replay --session <session-id>
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
# run a real Letta session here that causes at least one recall and one miss
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db finish-letta-capture \
  --capture-id <capture-id> \
  --runtime-trace <path-to-runtime-trace.jsonl>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect --session <session-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db replay --session <session-id>
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
- confirm that MemFS Doctor can generate the runtime trace itself while you use terminal Letta normally

Commands:

```bash
PYTHONPATH=src python3 -m memfs_doctor.cli.main start-letta-capture --agent <agent-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db record-letta-runtime \
  --capture-id <capture-id> \
  --auto-finish \
  -- letta
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect --session <session-id>
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db metrics --session <session-id> --json
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db replay --session <session-id>
```

Suggested Letta interaction:
1. ask one recall-style question for a fact the agent should know
2. ask one question for a fact the agent does not know
3. optionally issue one remember/update command in the same session
4. exit Letta cleanly

Expected result:
- a runtime trace file is written under `.memfs_doctor/runtime/`
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db report \
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db compare-sessions \
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect-retrieval \
  --session <session-id> \
  --json

PYTHONPATH=src python3 -m memfs_doctor.cli.main --db /tmp/memfs-doctor-session.db inspect-retrieval \
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
PYTHONPATH=src python3 -m memfs_doctor.cli.main replay \
  --session <session-id>

PYTHONPATH=src python3 -m memfs_doctor.cli.main inspect-step \
  --session <session-id> \
  --step <step-number> \
  --json

PYTHONPATH=src python3 -m memfs_doctor.cli.main diff \
  --session <session-id> \
  --before-step <earlier-step> \
  --after-step <later-step> \
  --json

PYTHONPATH=src python3 -m memfs_doctor.cli.main replay \
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

## Manual Test Notes Template

Use this template after each manual run:

```text
Date:
Phase:
Scenario:
Trace source:

Observed Letta behavior:
- ...

Observed MemFS Doctor output:
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
