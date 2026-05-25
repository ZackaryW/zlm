from __future__ import annotations

from pathlib import Path
from typing import Any

from zlm.core import SQLiteMemoryContext
from zlm.utils import require_session_id


class Zlm:
    def __init__(
        self,
        db_path: str | Path | None = None,
        session_id: str | None = None,
        max_sessions: int = 5,
        max_entries: int = 15,
    ) -> None:
        self._context = SQLiteMemoryContext(
            db_path=db_path,
            max_sessions=max_sessions,
            max_entries=max_entries,
        )
        self._session_id = session_id

    @property
    def context(self) -> SQLiteMemoryContext:
        return self._context

    @property
    def db_path(self) -> Path:
        return self._context.db_path

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def append(self, entry_type: str, body: Any, session_id: str | None = None) -> None:
        resolved_session_id = require_session_id(session_id or self._session_id)
        self._context.append(
            resolved_session_id,
            {"type": entry_type, "body": body},
        )
        if session_id is None:
            self._session_id = resolved_session_id

    def get(self, session_id: str | None = None) -> list[dict[str, Any]]:
        resolved_session_id = require_session_id(session_id or self._session_id)
        if session_id is None:
            self._session_id = resolved_session_id
        return self._context.get_session_memory(resolved_session_id)

    def create_session(self) -> str:
        session_id = self._context.create_session()
        self._session_id = session_id
        return session_id

    def close(self) -> None:
        self._context.close()

    def __enter__(self) -> Zlm:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()