from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from memops.core.events import MemoryEvent, SessionRecord


DEFAULT_DB_PATH = Path(".memfs_doctor") / "session.db"


class SQLiteEventStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT UNIQUE NOT NULL,
                    kind TEXT NOT NULL,
                    framework TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source TEXT NOT NULL,
                    memory_id TEXT,
                    related_memory_ids TEXT NOT NULL,
                    query TEXT,
                    before_json TEXT,
                    after_json TEXT,
                    metadata_json TEXT NOT NULL,
                    latency_ms REAL,
                    tokens_loaded INTEGER,
                    score REAL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_events_session_timestamp
                ON events (session_id, timestamp, id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS health_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    capture_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    framework TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    UNIQUE(capture_id, turn_index)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_snapshots_session_turn
                ON health_snapshots (session_id, turn_index)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_health_snapshots_capture_turn
                ON health_snapshots (capture_id, turn_index)
                """
            )

    def ingest_events(self, events: list[MemoryEvent]) -> int:
        if not events:
            return 0

        with self.connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO events (
                    event_id, kind, framework, agent_id, session_id, timestamp, source,
                    memory_id, related_memory_ids, query, before_json, after_json,
                    metadata_json, latency_ms, tokens_loaded, score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        event.event_id,
                        event.kind.value,
                        event.framework,
                        event.agent_id,
                        event.session_id,
                        event.timestamp,
                        event.source,
                        event.memory_id,
                        json.dumps(event.related_memory_ids),
                        event.query,
                        json.dumps(event.before) if event.before is not None else None,
                        json.dumps(event.after) if event.after is not None else None,
                        json.dumps(event.metadata),
                        event.latency_ms,
                        event.tokens_loaded,
                        event.score,
                    )
                    for event in events
                ],
            )
            return conn.total_changes

    def list_sessions(self) -> list[SessionRecord]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    framework,
                    agent_id,
                    MIN(CASE WHEN kind = 'session_started' THEN timestamp END) AS started_at,
                    MAX(CASE WHEN kind = 'session_ended' THEN timestamp END) AS ended_at,
                    COUNT(*) AS event_count
                FROM events
                GROUP BY session_id, framework, agent_id
                ORDER BY COALESCE(started_at, MIN(timestamp)) DESC
                """
            ).fetchall()
        return [
            SessionRecord(
                session_id=row[0],
                framework=row[1],
                agent_id=row[2],
                started_at=row[3],
                ended_at=row[4],
                event_count=row[5],
            )
            for row in rows
        ]

    def latest_session_ids(self, limit: int = 1) -> list[str]:
        sessions = self.list_sessions()
        return [session.session_id for session in sessions[:limit]]

    def get_session_events(self, session_id: str) -> list[MemoryEvent]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    event_id, kind, framework, agent_id, session_id, timestamp, source,
                    memory_id, related_memory_ids, query, before_json, after_json,
                    metadata_json, latency_ms, tokens_loaded, score
                FROM events
                WHERE session_id = ?
                ORDER BY timestamp ASC, id ASC
                """,
                (session_id,),
            ).fetchall()

        events: list[MemoryEvent] = []
        for row in rows:
            events.append(
                MemoryEvent.from_dict(
                    {
                        "event_id": row[0],
                        "kind": row[1],
                        "framework": row[2],
                        "agent_id": row[3],
                        "session_id": row[4],
                        "timestamp": row[5],
                        "source": row[6],
                        "memory_id": row[7],
                        "related_memory_ids": json.loads(row[8]),
                        "query": row[9],
                        "before": json.loads(row[10]) if row[10] else None,
                        "after": json.loads(row[11]) if row[11] else None,
                        "metadata": json.loads(row[12]),
                        "latency_ms": row[13],
                        "tokens_loaded": row[14],
                        "score": row[15],
                    }
                )
            )
        return events

    def upsert_health_snapshot(
        self,
        *,
        capture_id: str,
        session_id: str,
        framework: str,
        agent_id: str,
        turn_index: int,
        query: str,
        status: str,
        updated_at: str,
        metrics: dict[str, Any],
        findings: list[dict[str, Any]],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO health_snapshots (
                    capture_id, session_id, framework, agent_id, turn_index,
                    query, status, updated_at, metrics_json, findings_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(capture_id, turn_index) DO UPDATE SET
                    query = excluded.query,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    metrics_json = excluded.metrics_json,
                    findings_json = excluded.findings_json
                """,
                (
                    capture_id,
                    session_id,
                    framework,
                    agent_id,
                    turn_index,
                    query,
                    status,
                    updated_at,
                    json.dumps(metrics, sort_keys=True),
                    json.dumps(findings, sort_keys=True),
                ),
            )

    def list_health_snapshots(self, session_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    capture_id, session_id, framework, agent_id, turn_index, query,
                    status, updated_at, metrics_json, findings_json
                FROM health_snapshots
                WHERE session_id = ? OR capture_id = ?
                ORDER BY turn_index ASC, id ASC
                """,
                (session_id, session_id),
            ).fetchall()
        return [
            {
                "capture_id": row[0],
                "session_id": row[1],
                "framework": row[2],
                "agent_id": row[3],
                "turn_index": row[4],
                "query": row[5],
                "status": row[6],
                "updated_at": row[7],
                "metrics": json.loads(row[8]),
                "findings": json.loads(row[9]),
            }
            for row in rows
        ]

    def list_snapshot_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                WITH ranked AS (
                    SELECT
                        capture_id,
                        session_id,
                        framework,
                        agent_id,
                        turn_index,
                        query,
                        status,
                        updated_at,
                        ROW_NUMBER() OVER (PARTITION BY session_id ORDER BY turn_index DESC, id DESC) AS rn
                    FROM health_snapshots
                )
                SELECT
                    capture_id, session_id, framework, agent_id, turn_index, query, status, updated_at
                FROM ranked
                WHERE rn = 1
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "capture_id": row[0],
                "session_id": row[1],
                "framework": row[2],
                "agent_id": row[3],
                "turn_index": row[4],
                "query": row[5],
                "status": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]

    def count_health_snapshots(self, session_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM health_snapshots
                WHERE session_id = ? OR capture_id = ?
                """,
                (session_id, session_id),
            ).fetchone()
        return int(row[0] if row else 0)

    def total_health_snapshot_count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM health_snapshots").fetchone()
        return int(row[0] if row else 0)

    def total_event_count(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0] if row else 0)
