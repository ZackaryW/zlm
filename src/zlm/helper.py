from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from zlm.core import SQLiteMemoryContext
from zlm.utils import CWD_OVERRIDE_ENV, ensure_session_id, resolve_session_id, resolve_workspace_root


class Zlm:
    def __init__(
        self,
        db_path: str | Path | None = None,
        workspace_hash: str | None = None,
        max_sessions: int = 5,
        max_entries: int = 15,
    ) -> None:
        self._context = SQLiteMemoryContext(
            db_path=db_path,
            max_sessions=max_sessions,
            max_entries=max_entries,
        )
        self._workspace_hash = workspace_hash
        self._adopted_path: Path | None = None
        self._session_id: str | None = None

    @property
    def context(self) -> SQLiteMemoryContext:
        return self._context

    @property
    def db_path(self) -> Path:
        return self._context.db_path

    @property
    def workspace_root(self) -> Path:
        return resolve_workspace_root(self._adopted_path)

    @property
    def workspace_hash(self) -> str:
        return self._workspace_hash or self._context._derive_workspace_hash(self._adopted_path)

    def _resolved_workspace_hash(self) -> str | None:
        if self._workspace_hash is not None:
            return self._workspace_hash

        if self._adopted_path is not None:
            return self._context._derive_workspace_hash(self._adopted_path)

        return None

    def append(self, entry_type: str, body: Any) -> None:
        session_id = ensure_session_id(
            self._context,
            session_id=self._session_id,
            workspace_hash=self._resolved_workspace_hash(),
        )
        self._session_id = session_id
        self._context.append(
            session_id,
            {"type": entry_type, "body": body},
            workspace_hash=self._resolved_workspace_hash(),
        )

    def get(self, session_id: str | None = None) -> list[dict[str, Any]]:
        resolved_session_id = resolve_session_id(
            self._context,
            session_id=session_id or self._session_id,
            workspace_hash=self._resolved_workspace_hash(),
        )
        return self._context.get_session_memory(
            resolved_session_id,
            workspace_hash=self._resolved_workspace_hash(),
        )

    def swap(self) -> str:
        session_id = self._context.create_session(workspace_hash=self._resolved_workspace_hash())
        self._session_id = session_id
        return session_id

    def adopt(self, path: str | Path) -> Path:
        workspace_root = resolve_workspace_root(path)
        self._adopted_path = workspace_root
        self._session_id = None
        os.environ[CWD_OVERRIDE_ENV] = str(workspace_root)
        return workspace_root

    def close(self) -> None:
        self._context.close()

    def __enter__(self) -> Zlm:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()