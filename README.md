<h1 align="center">MemOps</h1>

<p align="center">
  Observability and regression analysis for persistent AI memory systems.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/CLI-First-1F2937" alt="CLI First">
  <img src="https://img.shields.io/badge/SQLite-Trace%20Store-003B57?logo=sqlite&logoColor=white" alt="SQLite Trace Store">
  <img src="https://img.shields.io/badge/Letta-Adapter%20First-0F766E" alt="Letta Adapter First">
  <img src="https://img.shields.io/badge/Status-Phase%208%20Implemented-15803D" alt="Status Phase 8 Implemented">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/kedarvartak/doctor-memory/main/examples/banner.png" alt="MemOps banner">
</p>

## What Is MemOps?

MemOps is an observability and regression analysis toolkit for persistent AI memory systems.

It captures memory activity from AI agents, reconstructs session history, computes memory-health metrics, and detects regressions between runs.

The project is currently CLI-first and Letta-first, with a framework-neutral event architecture designed for future adapters.

## Why It Exists

Persistent agents can degrade in ways normal infra dashboards do not explain:

- retrieval becomes empty, stale, or noisy
- memory rewrites become unstable
- duplicate or contradictory facts accumulate
- token pressure and latency rise over time
- candidate runs quietly regress against known-good baselines

MemOps turns those failures into inspectable signals, replayable traces, and regression reports.

## Core Capabilities

| Capability | Description |
|------------|-------------|
| Event Capture | Collects normalized memory events from agent frameworks |
| Session Replay | Reconstructs memory evolution step-by-step |
| Health Metrics | Computes stability, retrieval, and memory-pressure metrics |
| Regression Analysis | Compares baseline vs candidate memory behavior |
| Retrieval Inspection | Surfaces stale, noisy, and token-heavy recalls |
| Local Trace Store | Uses SQLite-backed append-only event storage |
| Dashboard | Exposes session timelines, incident signals, and root-cause hints |
| Adapter Model | Keeps the core framework-neutral and Letta-first |

## Memory Evaluation Pipeline

```text
Agent Runtime
      ↓
Memory Event Capture
      ↓
Normalized Event Store
      ↓
Session Replay Engine
      ↓
Health Metric Computation
      ↓
Regression Detection
      ↓
Developer Reports + Dashboard
```

## Memory Health Metrics

| Metric | What It Detects | Why It Matters |
|--------|------------------|----------------|
| `memory_churn_rate` | Excessive rewrites | Signals unstable memory behavior |
| `duplicate_rate` | Repeated or near-identical facts | Indicates noisy storage |
| `contradiction_score` | Conflicting memory values | Strong corruption or poisoning signal |
| `stale_recall_rate` | Outdated recall usage | Causes incorrect or misleading answers |
| `empty_retrieval_rate` | Retrieval attempts with no useful memory | Means memory exists but is not usable |
| `retrieval_latency_ms_avg` | Slow memory access | Suggests scaling or retrieval-quality problems |
| `retrieval_count` | How much the session exercised memory | Helps judge confidence in the run |
| `write_count` | Raw mutation volume | Exposes write pressure and instability |
| `context_pressure_score` | Excess memory load in context | Increases model confusion risk |
| `memory_tokens_loaded_total` | Total memory payload injected into the model | Can degrade reasoning quality |

## Regression Analysis

MemOps supports baseline-vs-candidate evaluation for persistent-memory systems.

It can:

- compare two stored sessions
- compare two trace files directly
- apply thresholded regression policies
- return non-zero exit codes for CI and automated benchmarks

This is the main loop for validating memory-policy changes, retrieval changes, adapter changes, and cross-agent benchmarking.

## Example Findings

### Example Regression Output

| Metric | Baseline | Candidate | Delta |
|--------|----------|-----------|-------|
| `contradiction_score` | `0.03` | `0.27` | `+0.24` |
| `stale_recall_rate` | `0.04` | `0.21` | `+0.17` |
| `retrieval_latency_ms_avg` | `112ms` | `391ms` | `+279ms` |
| `memory_churn_rate` | `0.18` | `0.46` | `+0.28` |

Result: regression detected.

### Example Debug Questions

MemOps is designed to answer questions like:

- Which turn first pushed the session from healthy to warning?
- Which write introduced the contradiction?
- Which retrieval loaded stale memory?
- Did a candidate memory policy reduce churn or make it worse?
- Did the agent fail because of session drift or because the memory layer itself degraded?

## Current Status

MemOps already supports:

- normalized append-only memory events
- local trace storage and deterministic replay
- retrieval-path inspection
- health thresholds and regression checks
- baseline-vs-candidate comparison
- per-turn health snapshots
- a local dashboard for observability and root-cause inspection

It is already useful for:

- local agent memory debugging
- regression-oriented testing
- stress testing retrieval quality
- detecting when a long-lived agent starts drifting or poisoning itself

## Roadmap

- Phase 1: core event model and local storage
- Phase 2: Letta adapter MVP and capture workflow
- Phase 3: metrics, health reports, and session comparison
- Phase 4: retrieval explainability and causal recall inspection
- Phase 5: replay engine, step inspection, and offline snapshot diffing
- Phase 6: alerts, regression checks, and CI hooks
- Phase 7: local dashboard foundation for memory observability
- Phase 8: AI agent observability layer for drift, poisoning, and root-cause debugging

Detailed docs:

- [Roadmap](https://github.com/kedarvartak/doctor-memory/blob/main/docs/roadmap.md)
- [Testing Guide](https://github.com/kedarvartak/doctor-memory/blob/main/docs/testing.md)
- [Versioning Log](https://github.com/kedarvartak/doctor-memory/blob/main/docs/versioning.md)
- [Publishing Guide](https://github.com/kedarvartak/doctor-memory/blob/main/docs/publish.md)

## Philosophy

MemOps is being built as serious infrastructure for memory systems:

- CLI-first before platform-heavy
- framework-neutral at the core
- replayable before abstract
- metrics-driven rather than intuition-driven
- test-gated at every phase

Recommended local install:

```bash
uv pip install -e .
```

Planned public install target:

```bash
uv pip install memops
```
