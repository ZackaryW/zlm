from pathlib import Path

import pytest

from zlm.core.memory_context import SQLiteMemoryContext
from zlm.utils.storage import default_db_path


def test_context_uses_temp_db_path_by_default() -> None:
    context = SQLiteMemoryContext()

    assert context.db_path == default_db_path()

    context.close()


def test_context_initializes_expected_tables_indexes_and_pragmas(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    table_rows = context.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('sessions', 'memories') ORDER BY name"
    ).fetchall()
    index_rows = context.connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%' ORDER BY name"
    ).fetchall()
    journal_mode = context.connection.execute("PRAGMA journal_mode;").fetchone()[0]
    synchronous = context.connection.execute("PRAGMA synchronous;").fetchone()[0]
    foreign_keys = context.connection.execute("PRAGMA foreign_keys;").fetchone()[0]

    assert [row[0] for row in table_rows] == ["memories", "sessions"]
    assert [row[0] for row in index_rows] == [
        "idx_memories_session_id",
        "idx_memories_workspace_session",
        "idx_sessions_workspace_last_seen",
    ]
    assert journal_mode == "wal"
    assert synchronous == 1
    assert foreign_keys == 0

    context.close()


def test_list_sessions_and_latest_session_are_empty_initially(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    assert context.list_sessions(workspace_hash="workspace-a") == []
    assert context.latest_session(workspace_hash="workspace-a") is None

    context.close()


def test_append_returns_retained_session_window_in_order(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    session_id = context.create_session(workspace_hash="workspace-a")

    for value in range(17):
        context.append(
            session_id,
            {"type": "score", "body": value},
            workspace_hash="workspace-a",
        )

    assert context.get_session_memory(session_id, workspace_hash="workspace-a") == [
        {"type": "score", "body": value}
        for value in range(2, 17)
    ]

    context.close()


def test_append_raises_for_unknown_session(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="unknown session_id"):
        context.append("missing-session", {"type": "score", "body": 1}, workspace_hash="workspace-a")

    context.close()


def test_append_uses_derived_workspace_hash_when_not_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    workspace = tmp_path / "repo"
    nested_dir = workspace / "a" / "b"
    nested_dir.mkdir(parents=True)
    (workspace / ".git").mkdir()
    monkeypatch.chdir(nested_dir)

    session_id = context.create_session()
    context.append(session_id, {"type": "verdict", "body": "retry"})

    assert context.latest_session() == session_id
    assert context.get_session_memory(session_id) == [{"type": "verdict", "body": "retry"}]

    context.close()


def test_get_session_memory_raises_for_unknown_session(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory("missing-session", workspace_hash="workspace-a")

    context.close()


def test_get_session_memory_rejects_workspace_mismatch(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    session_id = context.create_session(workspace_hash="workspace-a")

    with pytest.raises(ValueError, match="session does not belong to workspace"):
        context.get_session_memory(session_id, workspace_hash="workspace-b")

    context.close()


def test_append_evicts_old_sessions_and_deletes_their_memories(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    timestamps = iter(range(1, 20))
    context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]

    session_ids = [context.create_session(workspace_hash="workspace-a") for _ in range(5)]
    context.append(
        session_ids[0],
        {"type": "flag", "body": True},
        workspace_hash="workspace-a",
    )

    new_session = context.create_session(workspace_hash="workspace-a")
    context.append(
        new_session,
        {"type": "flag", "body": "new"},
        workspace_hash="workspace-a",
    )

    assert context.list_sessions(workspace_hash="workspace-a") == [
        new_session,
        session_ids[0],
        session_ids[4],
        session_ids[3],
        session_ids[2],
    ]
    assert context.latest_session(workspace_hash="workspace-a") == new_session

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory(session_ids[1], workspace_hash="workspace-a")

    assert context.get_session_memory(new_session, workspace_hash="workspace-a") == [
        {"type": "flag", "body": "new"}
    ]

    context.close()


def test_create_session_prunes_old_sessions_inline(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    timestamps = iter(range(1, 10))
    context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]

    session_ids = [context.create_session(workspace_hash="workspace-a") for _ in range(6)]

    assert context.list_sessions(workspace_hash="workspace-a") == list(reversed(session_ids[1:]))

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory(session_ids[0], workspace_hash="workspace-a")

    context.close()


def test_append_rejects_workspace_mismatch(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    session_id = context.create_session(workspace_hash="workspace-a")

    with pytest.raises(ValueError, match="session does not belong to workspace"):
        context.append(
            session_id,
            {"type": "score", "body": 1},
            workspace_hash="workspace-b",
        )

    context.close()


def test_workspaces_are_retained_independently(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    session_a = context.create_session(workspace_hash="workspace-a")
    session_b = context.create_session(workspace_hash="workspace-b")

    context.append(session_a, {"type": "flag", "body": True}, workspace_hash="workspace-a")
    context.append(session_b, {"type": "flag", "body": False}, workspace_hash="workspace-b")

    assert context.list_sessions(workspace_hash="workspace-a") == [session_a]
    assert context.list_sessions(workspace_hash="workspace-b") == [session_b]
    assert context.get_session_memory(session_a, workspace_hash="workspace-a") == [{"type": "flag", "body": True}]
    assert context.get_session_memory(session_b, workspace_hash="workspace-b") == [{"type": "flag", "body": False}]

    context.close()


def test_retained_state_remains_available_after_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    first_context = SQLiteMemoryContext(db_path)
    session_id = first_context.create_session(workspace_hash="workspace-a")
    first_context.append(
        session_id,
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}},
        workspace_hash="workspace-a",
    )
    first_context.close()

    second_context = SQLiteMemoryContext(db_path)

    assert second_context.get_session_memory(session_id, workspace_hash="workspace-a") == [
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}}
    ]

    second_context.close()