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
