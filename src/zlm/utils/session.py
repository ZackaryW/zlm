from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zlm.core.memory_context import SQLiteMemoryContext


def resolve_session_id(
    memory_context: SQLiteMemoryContext,
    session_id: str | None = None,
    workspace_hash: str | None = None,
) -> str:
    if session_id is not None:
        return session_id

    resolved_session_id = memory_context.latest_session(workspace_hash=workspace_hash)
    if resolved_session_id is None:
        raise ValueError("no session found for current workspace")

    return resolved_session_id


def ensure_session_id(
    memory_context: SQLiteMemoryContext,
    session_id: str | None = None,
    workspace_hash: str | None = None,
) -> str:
    if session_id is not None:
        return session_id

    resolved_session_id = memory_context.latest_session(workspace_hash=workspace_hash)
    if resolved_session_id is not None:
        return resolved_session_id

    return memory_context.create_session(workspace_hash=workspace_hash)