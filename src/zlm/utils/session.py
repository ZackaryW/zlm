from __future__ import annotations


def require_session_id(session_id: str | None) -> str:
    if session_id is None:
        raise ValueError("session_id is required")

    return session_id