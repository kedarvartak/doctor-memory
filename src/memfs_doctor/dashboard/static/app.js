import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18";
import { createRoot } from "https://esm.sh/react-dom@18/client";

const h = React.createElement;
const POLL_MS = 2000;

function statusClass(status) {
  if (status === "healthy" || status === "PASS") return "pass";
  if (status === "warning" || status === "WARN") return "warn";
  return "fail";
}

function statusLabel(status) {
  if (status === "healthy" || status === "PASS") return "PASS";
  if (status === "warning" || status === "WARN") return "WARN";
  return "FAIL";
}

function Sparkline({ values, stroke }) {
  const points = useMemo(() => {
    if (!values.length) return "";
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const range = max - min || 1;
    return values
      .map((value, index) => {
        const x = (index / Math.max(values.length - 1, 1)) * 100;
        const y = 90 - ((value - min) / range) * 70;
        return `${x},${y}`;
      })
      .join(" ");
  }, [values]);

  return h(
    "svg",
    { className: "sparkline", viewBox: "0 0 100 100", preserveAspectRatio: "none" },
    h("polyline", {
      fill: "none",
      stroke: stroke || "#22d98b",
      strokeWidth: "3",
      points,
      strokeLinejoin: "round",
      strokeLinecap: "round",
    })
  );
}

function SessionCard({ session, active, onSelect }) {
  return h(
    "div",
    {
      className: `session-card${active ? " active" : ""}`,
      onClick: () => onSelect(session.session_id),
    },
    h("div", { className: "session-id" }, session.session_id),
    h(
      "div",
      { className: "session-meta" },
      h("span", { className: `pill ${statusClass(session.live_status || "FAIL")}` }, statusLabel(session.live_status || "FAIL")),
      h("span", { className: "pill" }, `${session.framework}`),
      h("span", { className: "pill" }, `events ${session.event_count}`),
      session.last_turn_index != null ? h("span", { className: "pill" }, `turn ${session.last_turn_index}`) : null
    ),
    h(
      "div",
      { className: "tiny", style: { marginTop: "10px" } },
      session.last_query || session.agent_id
    )
  );
}

function MetricPanel({ title, value, caption }) {
  return h(
    "div",
    { className: "panel span-3" },
    h("div", { className: "panel-title" }, title),
    h("div", { className: "big-metric" }, value),
    h("div", { className: "metric-caption" }, caption)
  );
}

function TrendCard({ title, value, values, color }) {
  return h(
    "div",
    { className: "trend-card" },
    h("div", { className: "trend-label" }, title),
    h("div", { className: "trend-value" }, String(value ?? "-")),
    h(Sparkline, { values, stroke: color })
  );
}

function App() {
  const [overview, setOverview] = useState({ sessions: [] });
  const [selectedSession, setSelectedSession] = useState(window.location.hash.slice(1));
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    const syncFromHash = () => setSelectedSession(window.location.hash.slice(1));
    window.addEventListener("hashchange", syncFromHash);
    return () => window.removeEventListener("hashchange", syncFromHash);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const response = await fetch("/api/overview");
      const payload = await response.json();
      if (cancelled) return;
      setOverview(payload);
      if (!window.location.hash && payload.sessions.length) {
        window.location.hash = payload.sessions[0].session_id;
      }
    };
    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!selectedSession) return;
    let cancelled = false;
    const load = async () => {
      const response = await fetch(`/api/session/${encodeURIComponent(selectedSession)}`);
      const payload = await response.json();
      if (!cancelled) setDetail(payload);
    };
    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [selectedSession]);

  const snapshots = detail?.snapshots || [];
  const latestSnapshot = snapshots[snapshots.length - 1] || null;
  const report = detail?.report;
  const replay = detail?.replay;
  const metricSeries = (metric) => snapshots.map((item) => Number(item.metrics?.[metric] ?? 0));

  if (!overview.sessions.length) {
    return h("div", { className: "loading-state" }, "Waiting for MemFS Doctor session data...");
  }

  return h(
    "div",
    { className: "app-shell" },
    h(
      "aside",
      { className: "sidebar" },
      h(
        "div",
        { className: "brand" },
        h("div", { className: "brand-kicker" }, "MemFS Doctor"),
        h("div", { className: "brand-title" }, "Agent Health"),
        h("div", { className: "brand-subtitle" }, "CLI-native observability for Letta memory, replay, retrievals, and drift.")
      ),
      h("div", { className: "sidebar-section-title" }, "Sessions"),
      h(
        "div",
        { className: "session-list" },
        overview.sessions.map((session) =>
          h(SessionCard, {
            key: session.session_id,
            session,
            active: session.session_id === selectedSession,
            onSelect: (id) => {
              window.location.hash = id;
            },
          })
        )
      )
    ),
    h(
      "main",
      { className: "main" },
      !detail
        ? h("div", { className: "loading-state" }, "Loading session detail...")
        : h(
            React.Fragment,
            null,
            h(
              "section",
              { className: "hero" },
              h(
                "div",
                null,
                h("h1", null, selectedSession),
                h(
                  "p",
                  null,
                  "Per-turn health snapshots stream in while Letta is running. Once the session is auto-finished, replay, report, and retrieval views are populated from the same stored events."
                )
              ),
              latestSnapshot
                ? h("span", { className: `pill ${statusClass(latestSnapshot.status)}` }, statusLabel(latestSnapshot.status))
                : h("span", { className: "pill" }, "NO SNAPSHOT")
            ),
            h(
              "section",
              { className: "panel-grid" },
              h(MetricPanel, {
                title: "Turns Seen",
                value: snapshots.length,
                caption: latestSnapshot?.query || "No turn snapshots yet",
              }),
              h(MetricPanel, {
                title: "Writes",
                value: latestSnapshot?.metrics?.write_count ?? report?.metrics?.write_count ?? 0,
                caption: "Current write pressure",
              }),
              h(MetricPanel, {
                title: "Retrieval Latency",
                value: latestSnapshot?.metrics?.retrieval_latency_ms_avg ?? report?.metrics?.retrieval_latency_ms_avg ?? 0,
                caption: "Average ms",
              }),
              h(MetricPanel, {
                title: "Churn Rate",
                value: latestSnapshot?.metrics?.memory_churn_rate ?? report?.metrics?.memory_churn_rate ?? 0,
                caption: "Writes / total events",
              }),
              h(
                "div",
                { className: "panel span-8" },
                h("div", { className: "panel-title" }, "Metric Trends"),
                h(
                  "div",
                  { className: "trend-grid" },
                  h(TrendCard, {
                    title: "Memory Churn",
                    value: latestSnapshot?.metrics?.memory_churn_rate ?? 0,
                    values: metricSeries("memory_churn_rate"),
                    color: "#22d98b",
                  }),
                  h(TrendCard, {
                    title: "Retrieval Latency",
                    value: latestSnapshot?.metrics?.retrieval_latency_ms_avg ?? 0,
                    values: metricSeries("retrieval_latency_ms_avg"),
                    color: "#59d8ff",
                  }),
                  h(TrendCard, {
                    title: "Duplicate Rate",
                    value: latestSnapshot?.metrics?.duplicate_rate ?? 0,
                    values: metricSeries("duplicate_rate"),
                    color: "#ffbf47",
                  }),
                  h(TrendCard, {
                    title: "Contradiction Score",
                    value: latestSnapshot?.metrics?.contradiction_score ?? 0,
                    values: metricSeries("contradiction_score"),
                    color: "#ff5f56",
                  })
                )
              ),
              h(
                "div",
                { className: "panel span-4" },
                h("div", { className: "panel-title" }, "Issue Summary"),
                report?.findings?.length
                  ? h(
                      "div",
                      { className: "findings-list" },
                      report.findings.map((finding, index) =>
                        h(
                          "div",
                          { key: `${finding.metric}-${index}`, className: "finding" },
                          h("div", { className: "finding-title" }, `${finding.severity} / ${finding.metric}`),
                          h("div", { className: "finding-body" }, finding.message)
                        )
                      )
                    )
                  : h("div", { className: "tiny" }, "No threshold findings for this stored session yet.")
              ),
              h(
                "div",
                { className: "panel span-12" },
                h("div", { className: "panel-title" }, "Per-Turn Health Log"),
                h(
                  "div",
                  { className: "snapshot-table" },
                  h(
                    "table",
                    null,
                    h(
                      "thead",
                      null,
                      h(
                        "tr",
                        null,
                        h("th", null, "Turn"),
                        h("th", null, "Query"),
                        h("th", null, "Status"),
                        h("th", null, "Churn"),
                        h("th", null, "Latency"),
                        h("th", null, "Duplicates"),
                        h("th", null, "Updated")
                      )
                    ),
                    h(
                      "tbody",
                      null,
                      snapshots.map((item) =>
                        h(
                          "tr",
                          { key: `${item.turn_index}-${item.updated_at}` },
                          h("td", null, item.turn_index),
                          h("td", null, item.query),
                          h("td", null, h("span", { className: `pill ${statusClass(item.status)}` }, statusLabel(item.status))),
                          h("td", null, String(item.metrics.memory_churn_rate ?? 0)),
                          h("td", null, String(item.metrics.retrieval_latency_ms_avg ?? 0)),
                          h("td", null, String(item.metrics.duplicate_rate ?? 0)),
                          h("td", null, item.updated_at)
                        )
                      )
                    )
                  )
                )
              ),
              h(
                "div",
                { className: "panel span-6" },
                h("div", { className: "panel-title" }, "Replay Entry Points"),
                replay?.timeline?.length
                  ? h(
                      "div",
                      { className: "replay-list" },
                      replay.timeline.slice(-8).map((item) =>
                        h(
                          "div",
                          { key: `${item.step}-${item.timestamp}`, className: "replay-item" },
                          h("div", { className: "replay-step" }, `Step ${item.step} / ${item.kind}`),
                          h("div", { className: "replay-body" }, item.summary)
                        )
                      )
                    )
                  : h("div", { className: "tiny" }, "Replay becomes available after the session is ingested.")
              ),
              h(
                "div",
                { className: "panel span-6" },
                h("div", { className: "panel-title" }, "Retrieval Inspection"),
                detail?.retrievals?.traces?.length
                  ? h(
                      "div",
                      { className: "replay-list" },
                      detail.retrievals.traces.slice(-6).map((trace) =>
                        h(
                          "div",
                          { key: `${trace.step}-${trace.event_id}`, className: "replay-item" },
                          h("div", { className: "replay-step" }, `Step ${trace.step} / ${trace.kind}`),
                          h(
                            "div",
                            { className: "replay-body" },
                            `${trace.query || "-"} | noisy=${trace.likely_noisy} | stale=${trace.stale}`
                          )
                        )
                      )
                    )
                  : h("div", { className: "tiny" }, "No retrieval traces captured for this session.")
              )
            )
          )
    )
  );
}

createRoot(document.getElementById("root")).render(h(App));

