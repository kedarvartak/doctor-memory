# Memory Discipline TODO

## Goal

Reduce agent memory degradation by improving what gets written, how it gets updated, how it gets retrieved, and how the resulting behavior is validated.

## Implementation

- Tighten memory write policy.
  Only store durable facts, preferences, goals, constraints, and stable context.

- Reduce noisy rewrites.
  Do not rewrite memory unless something materially changed.

- Add duplicate prevention before commit.
  Reject near-identical writes instead of appending more memory noise.

- Prefer updates over parallel variants.
  When the same fact changes, update the existing memory instead of storing conflicting versions.

- Add contradiction guards.
  Detect conflicting values before they enter memory.

- Add freshness handling.
  Track recency so newer memory can override stale memory more safely.

- Improve retrieval selectivity.
  Retrieve fewer, higher-confidence memories rather than loading broad noisy context.

- Separate memory types where useful.
  Distinguish durable long-term facts from ephemeral conversational state.

- Add cleanup or compaction policy.
  Merge duplicates, remove stale memory, and compress low-value detail over time.

## Metrics To Improve

- `memory_churn_rate`
- `duplicate_rate`
- `contradiction_score`
- `stale_recall_rate`
- `empty_retrieval_rate`
- `retrieval_latency_ms_avg`
- `memory_tokens_loaded_total`
- `context_pressure_score`

## Validation Strategy

- Establish a clean baseline session suite.
  Use repeatable prompts and similar session structure.

- Apply one memory-discipline change at a time.
  Avoid changing multiple variables if the goal is attribution.

- Re-run the same benchmark sessions after the change.
  Compare candidate behavior against the baseline.

- Use health reports and regression checks to confirm improvement.
  Improvement should appear in metrics, not only intuition.

- Use replay to inspect where degradation first appears.
  The bad write, contradiction, or noisy recall should happen later or disappear.

- Use the dashboard to confirm that `WARN` or `FAIL` states occur less often, later, or not at all.

## Benchmark Scenarios

- Clean fact recall
- Correction and update flow
- Conflicting information flow
- Long-session drift
- Retrieval stress
- Noisy conversational memory pressure

## Success Criteria

- Lower `memory_churn_rate`
- Lower `duplicate_rate`
- Lower or flat `contradiction_score`
- Lower `stale_recall_rate`
- Lower `retrieval_latency_ms_avg` or acceptable stability
- No regression in `empty_retrieval_rate`
- Fewer `WARN` and `FAIL` states in the dashboard and reports
- Replay shows fewer suspicious writes and cleaner memory evolution
