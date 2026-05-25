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
        "idx_sessions_last_seen",
    ]
    assert journal_mode == "wal"
    assert synchronous == 1
    assert foreign_keys == 0

    context.close()


def test_list_sessions_and_latest_session_are_empty_initially(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    assert context.list_sessions() == []
    assert context.latest_session() is None

    context.close()


def test_append_returns_retained_session_window_in_order(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    session_id = context.create_session()

    for value in range(17):
        context.append(session_id, {"type": "score", "body": value})

    assert context.get_session_memory(session_id) == [
        {"type": "score", "body": value}
        for value in range(2, 17)
    ]

    context.close()


def test_append_raises_for_unknown_session(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="unknown session_id"):
        context.append("missing-session", {"type": "score", "body": 1})

    context.close()


def test_append_updates_latest_session(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    session_id = context.create_session()
    context.append(session_id, {"type": "verdict", "body": "retry"})

    assert context.latest_session() == session_id
    assert context.get_session_memory(session_id) == [{"type": "verdict", "body": "retry"}]

    context.close()


def test_get_session_memory_raises_for_unknown_session(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory("missing-session")

    context.close()


def test_append_evicts_old_sessions_and_deletes_their_memories(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    timestamps = iter(range(1, 20))
    context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]

    session_ids = [context.create_session() for _ in range(5)]
    context.append(session_ids[0], {"type": "flag", "body": True})

    new_session = context.create_session()
    context.append(new_session, {"type": "flag", "body": "new"})

    assert context.list_sessions() == [
        new_session,
        session_ids[0],
        session_ids[4],
        session_ids[3],
        session_ids[2],
    ]
    assert context.latest_session() == new_session

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory(session_ids[1])

    assert context.get_session_memory(new_session) == [
        {"type": "flag", "body": "new"}
    ]

    context.close()


def test_create_session_prunes_old_sessions_inline(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    timestamps = iter(range(1, 10))
    context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]

    session_ids = [context.create_session() for _ in range(6)]

    assert context.list_sessions() == list(reversed(session_ids[1:]))

    with pytest.raises(ValueError, match="unknown session_id"):
        context.get_session_memory(session_ids[0])

    context.close()


def test_sessions_are_retained_independently(tmp_path: Path) -> None:
    context = SQLiteMemoryContext(tmp_path / "memory.db")
    session_a = context.create_session()
    session_b = context.create_session()

    context.append(session_a, {"type": "flag", "body": True})
    context.append(session_b, {"type": "flag", "body": False})

    assert context.list_sessions() == [session_b, session_a]
    assert context.get_session_memory(session_a) == [{"type": "flag", "body": True}]
    assert context.get_session_memory(session_b) == [{"type": "flag", "body": False}]

    context.close()


def test_retained_state_remains_available_after_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    first_context = SQLiteMemoryContext(db_path)
    session_id = first_context.create_session()
    first_context.append(
        session_id,
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}},
    )
    first_context.close()

    second_context = SQLiteMemoryContext(db_path)

    assert second_context.get_session_memory(session_id) == [
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}}
    ]

    second_context.close()