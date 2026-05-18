from pathlib import Path

import pytest

from zlm.core.memory_context import SQLiteMemoryContext
from zlm.utils.session import ensure_session_id, resolve_session_id


def test_resolve_session_id_returns_explicit_session_id(tmp_path: Path) -> None:
    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        session_id = context.create_session(workspace_hash="workspace-a")

        assert resolve_session_id(context, session_id=session_id, workspace_hash="workspace-a") == session_id


def test_resolve_session_id_uses_latest_session_for_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        timestamps = iter([1, 2])
        context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]
        first_session = context.create_session()
        latest_session = context.create_session()

        assert resolve_session_id(context) == latest_session
        assert resolve_session_id(context, workspace_hash=context._derive_workspace_hash()) == latest_session
        assert first_session != latest_session


def test_resolve_session_id_raises_when_workspace_has_no_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        with pytest.raises(ValueError, match="no session found for current workspace"):
            resolve_session_id(context)


def test_ensure_session_id_creates_session_when_workspace_has_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        session_id = ensure_session_id(context)

        assert session_id == context.latest_session()


def test_ensure_session_id_reuses_latest_session_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        timestamps = iter([1, 2])
        context._now_ts = lambda: next(timestamps)  # type: ignore[method-assign]
        context.create_session()
        latest_session = context.create_session()

        assert ensure_session_id(context) == latest_session


def test_ensure_session_id_reuses_same_repo_session_from_different_subdirectories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    first_dir = repo_root / "a" / "b"
    second_dir = repo_root / "x" / "y"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    with SQLiteMemoryContext(tmp_path / "memory.db") as context:
        monkeypatch.chdir(first_dir)
        session_id = ensure_session_id(context)

        monkeypatch.chdir(second_dir)
        assert ensure_session_id(context) == session_id