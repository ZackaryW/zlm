from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any

from zlm.utils import (
    default_db_path,
    deserialize_entry,
    now_ts,
    serialize_entry,
    validate_entry,
)


class SQLiteMemoryContext:
    def __init__(
        self,
        db_path: str | Path | None = None,
        max_sessions: int = 5,
        max_entries: int = 15,
    ) -> None:
        self._db_path = default_db_path() if db_path is None else Path(db_path)
        self._max_sessions = max_sessions
        self._max_entries = max_entries
        self._conn = self._connect(self._db_path)
        self._init_db()

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def _connect(self, db_path: Path) -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=OFF;")
        return conn

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    payload BLOB NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_last_seen
                ON sessions(last_seen_at DESC, session_id DESC)
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_session_id
                ON memories(session_id, id DESC)
                """
            )

    def _now_ts(self) -> int:
        return now_ts()

    def _validate_entry(self, entry: object) -> dict[str, Any]:
        return validate_entry(entry)

    def _session_exists(self, session_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row is not None

    def _prune_session_entries(self, session_id: str) -> None:
        self._conn.execute(
            """
            DELETE FROM memories
            WHERE session_id = ?
              AND id NOT IN (
                SELECT id
                FROM memories
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
              )
            """,
            (session_id, session_id, self._max_entries),
        )

    def _find_evicted_sessions(self) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT session_id
            FROM sessions
            ORDER BY last_seen_at DESC, session_id DESC
            LIMIT -1 OFFSET ?
            """,
            (self._max_sessions,),
        ).fetchall()
        return [str(row["session_id"]) for row in rows]

    def _delete_sessions_and_memories(self, session_ids: list[str]) -> None:
        if not session_ids:
            return

        placeholders = ", ".join("?" for _ in session_ids)
        self._conn.execute(
            f"DELETE FROM memories WHERE session_id IN ({placeholders})",
            session_ids,
        )
        self._conn.execute(
            f"DELETE FROM sessions WHERE session_id IN ({placeholders})",
            session_ids,
        )

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        created_at = self._now_ts()

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO sessions(session_id, created_at, last_seen_at)
                VALUES(?, ?, ?)
                """,
                (session_id, created_at, created_at),
            )
            evicted_sessions = self._find_evicted_sessions()
            self._delete_sessions_and_memories(evicted_sessions)

        return session_id

    def append(
        self,
        session_id: str,
        entry: dict,
    ) -> None:
        if not self._session_exists(session_id):
            raise ValueError(f"unknown session_id: {session_id}")

        payload = serialize_entry(entry)
        updated_at = self._now_ts()

        with self._conn:
            self._conn.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
                (updated_at, session_id),
            )
            self._conn.execute(
                """
                INSERT INTO memories(session_id, created_at, payload)
                VALUES(?, ?, ?)
                """,
                (session_id, updated_at, payload),
            )
            self._prune_session_entries(session_id)
            evicted_sessions = self._find_evicted_sessions()
            self._delete_sessions_and_memories(evicted_sessions)

    def get_session_memory(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        if not self._session_exists(session_id):
            raise ValueError(f"unknown session_id: {session_id}")

        rows = self._conn.execute(
            """
            SELECT payload
            FROM memories
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, self._max_entries),
        ).fetchall()
        return [deserialize_entry(row["payload"]) for row in reversed(rows)]

    def list_sessions(self) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT session_id
            FROM sessions
            ORDER BY last_seen_at DESC, session_id DESC
            LIMIT ?
            """,
            (self._max_sessions,),
        ).fetchall()
        return [str(row["session_id"]) for row in rows]

    def latest_session(self) -> str | None:
        sessions = self.list_sessions()
        if not sessions:
            return None
        return sessions[0]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SQLiteMemoryContext:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()