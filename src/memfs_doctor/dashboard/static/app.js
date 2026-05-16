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

function formatMetric(value, digits = 2) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return "-";
  if (Math.abs(number) >= 1000) return number.toFixed(0);
  return number.toFixed(digits).replace(/\.00$/, "");
}

function formatTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
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
      stroke: stroke,
      strokeWidth: "3",
      points,
      strokeLinejoin: "round",
      strokeLinecap: "round",
    })
  );
}

function SessionCard({ session, active, onSelect }) {
  return h(
    "button",
    {
      type: "button",
      className: `session-card${active ? " active" : ""}`,
      onClick: () => onSelect(session.session_id),
    },
    h("div", { className: "session-card-top" }, [
      h("div", { key: "id", className: "session-id" }, session.session_id),
      h("span", { key: "status", className: `pill ${statusClass(session.live_status || "FAIL")}` }, statusLabel(session.live_status || "FAIL")),
    ]),
    h(
      "div",
      { className: "session-meta" },
      h("span", { className: "mini-meta" }, session.framework),
      h("span", { className: "mini-meta" }, `events ${session.event_count}`),
      session.last_turn_index != null ? h("span", { className: "mini-meta" }, `turn ${session.last_turn_index}`) : null
    ),
    h("div", { className: "session-footer" }, session.last_query || session.agent_id)
  );
}

function StatCard({ title, value, caption, tone }) {
  return h(
    "div",
    { className: `panel stat-card ${tone || ""}`.trim() },
    h("div", { className: "panel-title" }, title),
    h("div", { className: "stat-value" }, value),
    h("div", { className: "metric-caption" }, caption)
  );
}

function TrendCard({ title, value, values, color }) {
  return h(
    "div",
    { className: "trend-card" },
    h("div", { className: "trend-head" }, [
      h("div", { key: "label", className: "trend-label" }, title),
      h("div", { key: "value", className: "trend-value" }, formatMetric(value)),
    ]),
    h(Sparkline, { values, stroke: color })
  );
}

function FeedItem({ item }) {
  return h(
    "div",
    { className: `feed-item ${item.severity || ""}`.trim() },
    h("div", { className: "feed-item-head" }, [
      h("span", { key: "kind", className: "feed-kind" }, item.kind),
      item.status ? h("span", { key: "status", className: `pill ${statusClass(item.status)}` }, statusLabel(item.status)) : null,
      item.timestamp ? h("span", { key: "ts", className: "tiny" }, formatTimestamp(item.timestamp)) : null,
    ]),
    h("div", { className: "feed-title" }, item.title),
    item.body ? h("div", { className: "feed-body" }, item.body) : null
  );
}

function RootCauseCard({ title, value, note, tone }) {
  return h(
    "div",
    { className: `root-cause-card ${tone || ""}`.trim() },
    h("div", { className: "root-cause-label" }, title),
    h("div", { className: "root-cause-value" }, value),
    h("div", { className: "tiny" }, note)
  );
}

function HealthRail({ snapshots }) {
  if (!snapshots.length) {
    return h("div", { className: "tiny" }, "No turn snapshots yet.");
  }
  return h(
    "div",
    { className: "health-rail" },
    snapshots.map((item) =>
      h(
        "div",
        {
          key: `${item.turn_index}-${item.updated_at}`,
          className: `health-segment ${statusClass(item.status)}`,
          title: `Turn ${item.turn_index}: ${item.query}`,
        },
        h("span", null, item.turn_index)
      )
    )
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
  const retrievals = detail?.retrievals;

  const metricSeries = (metric) => snapshots.map((item) => Number(item.metrics?.[metric] ?? 0));

  const firstDegraded = useMemo(
    () => snapshots.find((item) => statusClass(item.status) !== "pass") || null,
    [snapshots]
  );

  const rootCauseCards = useMemo(() => {
    const duplicateStep = replay?.issue_first_seen?.duplicate;
    const contradictionStep = replay?.issue_first_seen?.contradiction;
    const noisiestRecall = retrievals?.top_problematic_recalls?.[0] || retrievals?.top_token_pressure_recalls?.[0] || null;
    return [
      {
        title: "First degradation",
        value: firstDegraded ? `Turn ${firstDegraded.turn_index}` : "None",
        note: firstDegraded ? firstDegraded.query : "No warning or fail snapshots yet.",
        tone: firstDegraded ? statusClass(firstDegraded.status) : "",
      },
      {
        title: "First duplicate",
        value: duplicateStep ? `Step ${duplicateStep}` : "None",
        note: duplicateStep ? "Replay flagged the first repeated memory state." : "No duplicate event observed.",
        tone: duplicateStep ? "warn" : "",
      },
      {
        title: "First contradiction",
        value: contradictionStep ? `Step ${contradictionStep}` : "None",
        note: contradictionStep ? "Replay flagged conflicting attribute values." : "No contradiction event observed.",
        tone: contradictionStep ? "fail" : "",
      },
      {
        title: "Most suspect recall",
        value: noisiestRecall ? `Step ${noisiestRecall.step}` : "None",
        note: noisiestRecall ? (noisiestRecall.query || noisiestRecall.kind) : "No problematic recall trace captured.",
        tone: noisiestRecall?.likely_noisy ? "warn" : "",
      },
    ];
  }, [firstDegraded, replay, retrievals]);

  const incidentFeed = useMemo(() => {
    const items = [];
    (report?.findings || []).forEach((finding, index) => {
      items.push({
        key: `finding-${index}`,
        kind: "threshold",
        title: `${finding.metric} breached`,
        body: finding.message,
        severity: finding.severity === "error" ? "fail" : "warn",
        status: finding.severity === "error" ? "FAIL" : "WARN",
      });
    });
    if (firstDegraded) {
      items.push({
        key: `degrade-${firstDegraded.turn_index}`,
        kind: "drift",
        title: `Health shifted at turn ${firstDegraded.turn_index}`,
        body: firstDegraded.query,
        severity: statusClass(firstDegraded.status),
        status: firstDegraded.status,
        timestamp: firstDegraded.updated_at,
      });
    }
    (retrievals?.top_problematic_recalls || []).slice(0, 3).forEach((trace) => {
      items.push({
        key: `recall-${trace.event_id}`,
        kind: "retrieval",
        title: trace.query || trace.kind,
        body: `stale=${trace.stale} noisy=${trace.likely_noisy} latency=${formatMetric(trace.latency_ms)}ms`,
        severity: trace.likely_noisy ? "warn" : "",
        timestamp: trace.timestamp,
      });
    });
    return items.slice(0, 8);
  }, [firstDegraded, report, retrievals]);

  const eventStream = useMemo(() => {
    const items = [];
    snapshots.forEach((item) => {
      items.push({
        key: `snapshot-${item.turn_index}-${item.updated_at}`,
        timestamp: item.updated_at,
        kind: "health",
        title: `Turn ${item.turn_index} ${statusLabel(item.status)}`,
        body: item.query,
        severity: statusClass(item.status),
        status: item.status,
      });
    });
    (replay?.timeline || []).forEach((entry) => {
      items.push({
        key: `replay-${entry.step}-${entry.timestamp}`,
        timestamp: entry.timestamp,
        kind: entry.kind,
        title: `Step ${entry.step} ${entry.summary}`,
        body: entry.flags?.length ? `flags: ${entry.flags.join(", ")}` : entry.query || "",
        severity: entry.flags?.includes("first_contradiction")
          ? "fail"
          : entry.flags?.includes("first_duplicate") || entry.flags?.includes("retrieval_miss")
            ? "warn"
            : "",
      });
    });
    (retrievals?.traces || []).forEach((trace) => {
      items.push({
        key: `trace-${trace.event_id}`,
        timestamp: trace.timestamp,
        kind: "retrieval",
        title: trace.query || trace.kind,
        body: `latency=${formatMetric(trace.latency_ms)}ms stale=${trace.stale} noisy=${trace.likely_noisy}`,
        severity: trace.likely_noisy ? "warn" : "",
      });
    });
    return items
      .sort((a, b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")))
      .slice(0, 16);
  }, [replay, retrievals, snapshots]);

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
        h("div", { className: "brand-title" }, "AI Agent Observability"),
        h(
          "div",
          { className: "brand-subtitle" },
          "Telemetry, drift detection, replay, retrieval inspection, and root-cause analysis for persistent agent memory."
        )
      ),
      h("div", { className: "sidebar-section-title" }, "Live sessions"),
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
              { className: "hero hero-obs" },
              h(
                "div",
                null,
                h("div", { className: "hero-kicker" }, "Observability overview"),
                h("h1", null, selectedSession),
                h(
                  "p",
                  null,
                  "Track when agent memory health changes, inspect the event stream, and isolate the earliest signal of drift, poisoning, contradiction, or recall failure."
                )
              ),
              h(
                "div",
                { className: "hero-pills" },
                h("span", { className: "pill" }, `db ${overview.db_path || "-"}`),
                h("span", { className: "pill" }, `snapshots ${overview.health_snapshot_count ?? 0}`),
                latestSnapshot
                  ? h("span", { className: `pill ${statusClass(latestSnapshot.status)}` }, statusLabel(latestSnapshot.status))
                  : h("span", { className: "pill fail" }, "NO SNAPSHOT")
              )
            ),
            h(
              "section",
              { className: "panel-grid" },
              h(StatCard, {
                title: "Turns observed",
                value: snapshots.length,
                caption: latestSnapshot?.query || "No health snapshots yet",
              }),
              h(StatCard, {
                title: "Current writes",
                value: formatMetric(latestSnapshot?.metrics?.write_count ?? report?.metrics?.write_count ?? 0, 0),
                caption: "Writes in the latest observed state",
                tone: (latestSnapshot?.metrics?.write_count ?? 0) > 0 ? "warn" : "",
              }),
              h(StatCard, {
                title: "Retrieval latency",
                value: `${formatMetric(latestSnapshot?.metrics?.retrieval_latency_ms_avg ?? report?.metrics?.retrieval_latency_ms_avg ?? 0)}ms`,
                caption: "Average retrieval response time",
                tone: (latestSnapshot?.metrics?.retrieval_latency_ms_avg ?? 0) > 1500 ? "warn" : "",
              }),
              h(StatCard, {
                title: "Memory churn",
                value: formatMetric(latestSnapshot?.metrics?.memory_churn_rate ?? report?.metrics?.memory_churn_rate ?? 0),
                caption: "Writes divided by total events",
                tone: (latestSnapshot?.metrics?.memory_churn_rate ?? 0) >= 0.4 ? "warn" : "",
              }),
              h(
                "div",
                { className: "panel span-8" },
                h("div", { className: "panel-title" }, "Health timeline"),
                h(HealthRail, { snapshots }),
                h(
                  "div",
                  { className: "timeline-summary" },
                  firstDegraded
                    ? `First degradation observed at turn ${firstDegraded.turn_index}: ${firstDegraded.query}`
                    : "No warning or fail states have been observed in this session."
                )
              ),
              h(
                "div",
                { className: "panel span-4" },
                h("div", { className: "panel-title" }, "Incident feed"),
                incidentFeed.length
                  ? h("div", { className: "feed-list" }, incidentFeed.map((item) => h(FeedItem, { key: item.key, item })))
                  : h("div", { className: "tiny" }, "No incidents or threshold breaches recorded yet.")
              ),
              h(
                "div",
                { className: "panel span-7" },
                h("div", { className: "panel-title" }, "Signal trends"),
                h(
                  "div",
                  { className: "trend-grid" },
                  h(TrendCard, {
                    title: "Memory churn",
                    value: latestSnapshot?.metrics?.memory_churn_rate ?? 0,
                    values: metricSeries("memory_churn_rate"),
                    color: "#7dd3fc",
                  }),
                  h(TrendCard, {
                    title: "Retrieval latency",
                    value: latestSnapshot?.metrics?.retrieval_latency_ms_avg ?? 0,
                    values: metricSeries("retrieval_latency_ms_avg"),
                    color: "#c4b5fd",
                  }),
                  h(TrendCard, {
                    title: "Duplicate rate",
                    value: latestSnapshot?.metrics?.duplicate_rate ?? 0,
                    values: metricSeries("duplicate_rate"),
                    color: "#fbbf24",
                  }),
                  h(TrendCard, {
                    title: "Contradiction score",
                    value: latestSnapshot?.metrics?.contradiction_score ?? 0,
                    values: metricSeries("contradiction_score"),
                    color: "#f87171",
                  })
                )
              ),
              h(
                "div",
                { className: "panel span-5" },
                h("div", { className: "panel-title" }, "Root cause map"),
                h(
                  "div",
                  { className: "root-cause-grid" },
                  rootCauseCards.map((item) =>
                    h(RootCauseCard, {
                      key: item.title,
                      title: item.title,
                      value: item.value,
                      note: item.note,
                      tone: item.tone,
                    })
                  )
                )
              ),
              h(
                "div",
                { className: "panel span-8" },
                h("div", { className: "panel-title" }, "Event stream"),
                eventStream.length
                  ? h("div", { className: "feed-list event-stream" }, eventStream.map((item) => h(FeedItem, { key: item.key, item })))
                  : h("div", { className: "tiny" }, "No live or replay events available yet.")
              ),
              h(
                "div",
                { className: "panel span-4" },
                h("div", { className: "panel-title" }, "Stored findings"),
                report?.findings?.length
                  ? h(
                      "div",
                      { className: "feed-list" },
                      report.findings.map((finding, index) =>
                        h(FeedItem, {
                          key: `${finding.metric}-${index}`,
                          item: {
                            kind: "health",
                            title: `${finding.metric} ${finding.severity}`,
                            body: finding.message,
                            severity: finding.severity === "error" ? "fail" : "warn",
                            status: finding.severity === "error" ? "FAIL" : "WARN",
                          },
                        })
                      )
                    )
                  : h("div", { className: "tiny" }, "No threshold findings for this stored session.")
              ),
              h(
                "div",
                { className: "panel span-12" },
                h("div", { className: "panel-title" }, "Per-turn health log"),
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
                          h("td", null, formatMetric(item.metrics.memory_churn_rate ?? 0)),
                          h("td", null, formatMetric(item.metrics.retrieval_latency_ms_avg ?? 0)),
                          h("td", null, formatMetric(item.metrics.duplicate_rate ?? 0)),
                          h("td", null, formatTimestamp(item.updated_at))
                        )
                      )
                    )
                  )
                )
              )
            )
          )
    )
  );
}

createRoot(document.getElementById("root")).render(h(App));
