import os
from pathlib import Path

import pytest

from zlm import Zlm
from zlm.utils import CWD_OVERRIDE_ENV


def test_helper_append_and_get_match_cli_style_usage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(CWD_OVERRIDE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        zlm.append("verdict", "hello")

        assert zlm.get() == [{"type": "verdict", "body": "hello"}]


def test_helper_swap_creates_new_current_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(CWD_OVERRIDE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        zlm.append("verdict", "before")
        first_session = zlm.swap()
        zlm.append("verdict", "after")

        assert zlm.get() == [{"type": "verdict", "body": "after"}]
        assert zlm.get(first_session) == [{"type": "verdict", "body": "after"}]


def test_helper_adopt_sets_env_override_to_git_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(CWD_OVERRIDE_ENV, raising=False)
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "pkg" / "feature"
    nested_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        adopted_root = zlm.adopt(nested_dir)

        assert adopted_root == repo_root.resolve()
        assert zlm.workspace_root == repo_root.resolve()
        assert zlm.workspace_hash == zlm.context._derive_workspace_hash(repo_root)
        assert os.environ[CWD_OVERRIDE_ENV] == str(repo_root.resolve())


def test_helper_adopt_allows_inheriting_memory_from_other_workspace_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv(CWD_OVERRIDE_ENV, raising=False)
    db_path = tmp_path / "memory.db"
    repo_root = tmp_path / "repo"
    source_dir = repo_root / "pkg" / "a"
    adopted_dir = tmp_path / "agent-worktree"
    source_dir.mkdir(parents=True)
    adopted_dir.mkdir()
    (repo_root / ".git").mkdir()

    monkeypatch.chdir(source_dir)
    with Zlm(db_path=db_path) as source_zlm:
        source_zlm.append("verdict", "retry")

    monkeypatch.chdir(adopted_dir)
    with Zlm(db_path=db_path) as adopted_zlm:
        adopted_zlm.adopt(source_dir)

        assert adopted_zlm.get() == [{"type": "verdict", "body": "retry"}]


def test_helper_allows_configuring_retention_limits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv(CWD_OVERRIDE_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with Zlm(db_path=tmp_path / "memory.db", max_sessions=2, max_entries=2) as zlm:
        first_session = zlm.swap()
        zlm.append("verdict", "first")

        second_session = zlm.swap()
        zlm.append("verdict", "second")
        zlm.append("verdict", "second-overflow")
        zlm.append("verdict", "second-latest")

        third_session = zlm.swap()
        zlm.append("verdict", "third")

        with pytest.raises(ValueError, match="unknown session_id"):
            zlm.get(first_session)

        assert zlm.get(second_session) == [
            {"type": "verdict", "body": "second-overflow"},
            {"type": "verdict", "body": "second-latest"},
        ]
        assert zlm.get() == [{"type": "verdict", "body": "third"}]
        assert zlm.context.list_sessions(zlm.workspace_hash) == [third_session, second_session]