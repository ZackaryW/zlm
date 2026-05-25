from pathlib import Path

import pytest

from zlm.core.memory_context import SQLiteMemoryContext
from zlm.utils.session import require_session_id


def test_require_session_id_returns_explicit_session_id() -> None:
    assert require_session_id("session-123") == "session-123"


def test_require_session_id_rejects_missing_session_id() -> None:
    with pytest.raises(ValueError, match="session_id is required"):
        require_session_id(None)


def test_context_latest_session_is_global_not_workspace_scoped(tmp_path: Path) -> None:
    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        timestamps = iter([1, 2])
        context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]
        first_session = context.create_session()
        latest_session = context.create_session()

        assert context.latest_session() == latest_session
        assert first_session != latest_session