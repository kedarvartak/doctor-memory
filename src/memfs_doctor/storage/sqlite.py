from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from memfs_doctor.core.events import MemoryEvent, SessionRecord


DEFAULT_DB_PATH = Path(".memfs_doctor") / "memfs_doctor.db"


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

