from pathlib import Path

import pytest

from zlm.utils.workspace import CWD_OVERRIDE_ENV, derive_workspace_hash, resolve_workspace_root


def test_resolve_workspace_root_uses_git_root_for_nested_directory(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "src" / "feature"
    nested_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    assert resolve_workspace_root(nested_dir) == repo_root.resolve()


def test_resolve_workspace_root_uses_parent_for_file_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    nested_file = repo_root / "src" / "feature" / "file.txt"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("x", encoding="utf-8")
    (repo_root / ".git").mkdir()

    assert resolve_workspace_root(nested_file) == repo_root.resolve()


def test_resolve_workspace_root_falls_back_to_resolved_path_without_git(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace" / "." / "child"
    workspace.mkdir(parents=True)

    assert resolve_workspace_root(workspace) == workspace.resolve()


def test_derive_workspace_hash_defaults_to_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    assert derive_workspace_hash() == derive_workspace_hash(workspace)


def test_derive_workspace_hash_is_stable_within_same_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "a" / "b"
    nested_file = repo_root / "a" / "c" / "file.txt"
    nested_dir.mkdir(parents=True)
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("x", encoding="utf-8")
    (repo_root / ".git").mkdir()

    assert derive_workspace_hash(repo_root) == derive_workspace_hash(nested_dir)
    assert derive_workspace_hash(repo_root) == derive_workspace_hash(nested_file)


def test_derive_workspace_hash_differs_across_distinct_workspaces(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    assert derive_workspace_hash(first) != derive_workspace_hash(second)


def test_resolve_workspace_root_uses_env_override_when_path_not_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "nested" / "child"
    other_dir = tmp_path / "elsewhere"
    nested_dir.mkdir(parents=True)
    other_dir.mkdir()
    (repo_root / ".git").mkdir()

    monkeypatch.chdir(other_dir)
    monkeypatch.setenv(CWD_OVERRIDE_ENV, str(nested_dir))

    assert resolve_workspace_root() == repo_root.resolve()


def test_derive_workspace_hash_uses_env_override_when_path_not_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "nested" / "child"
    other_dir = tmp_path / "elsewhere"
    nested_dir.mkdir(parents=True)
    other_dir.mkdir()
    (repo_root / ".git").mkdir()

    monkeypatch.chdir(other_dir)
    monkeypatch.setenv(CWD_OVERRIDE_ENV, str(nested_dir))

    assert derive_workspace_hash() == derive_workspace_hash(repo_root)