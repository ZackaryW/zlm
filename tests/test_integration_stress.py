from pathlib import Path

import orjson
from click.testing import CliRunner

from zlm import main
from zlm.utils import CWD_OVERRIDE_ENV


def test_cli_stress_integration_across_swap_and_adopted_workspaces(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    repo_a = tmp_path / "repo-a"
    repo_a_first = repo_a / "pkg" / "one"
    repo_a_second = repo_a / "pkg" / "two"
    repo_b = tmp_path / "repo-b"
    repo_b_dir = repo_b / "pkg" / "other"
    repo_a_first.mkdir(parents=True)
    repo_a_second.mkdir(parents=True)
    repo_b_dir.mkdir(parents=True)
    (repo_a / ".git").mkdir()
    (repo_b / ".git").mkdir()

    monkeypatch.chdir(repo_a_first)
    for value in range(120):
        append_result = runner.invoke(main, ["--db-path", str(db_path), "append", "score", str(value)])
        assert append_result.exit_code == 0

    repo_a_read = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert repo_a_read.exit_code == 0
    assert orjson.loads(repo_a_read.output) == [
        {"type": "score", "body": value}
        for value in range(105, 120)
    ]

    monkeypatch.chdir(repo_a_second)
    swap_result = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    new_session_id = swap_result.output.strip()
    empty_after_swap = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert swap_result.exit_code == 0
    assert new_session_id
    assert empty_after_swap.exit_code == 0
    assert empty_after_swap.output == "[]\n"

    append_after_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "verdict", '"after-swap"'],
    )
    current_after_swap = runner.invoke(main, ["--db-path", str(db_path), "get"])
    prior_session = runner.invoke(main, ["--db-path", str(db_path), "get", new_session_id])

    assert append_after_swap.exit_code == 0
    assert current_after_swap.exit_code == 0
    assert orjson.loads(current_after_swap.output) == [{"type": "verdict", "body": "after-swap"}]
    assert prior_session.exit_code == 0
    assert orjson.loads(prior_session.output) == [{"type": "verdict", "body": "after-swap"}]

    monkeypatch.chdir(repo_b_dir)
    other_workspace_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"repo-b"'])
    other_workspace_read = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert other_workspace_append.exit_code == 0
    assert other_workspace_read.exit_code == 0
    assert orjson.loads(other_workspace_read.output) == [{"type": "verdict", "body": "repo-b"}]

    adopt_result = runner.invoke(main, ["adopt", str(repo_a_first)])

    assert adopt_result.exit_code == 0
    assert str(repo_a.resolve()) in adopt_result.output

    monkeypatch.setenv(CWD_OVERRIDE_ENV, str(repo_a_first))
    adopted_read = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert adopted_read.exit_code == 0
    assert orjson.loads(adopted_read.output) == [{"type": "verdict", "body": "after-swap"}]

    monkeypatch.delenv(CWD_OVERRIDE_ENV)
    reverted_read = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert reverted_read.exit_code == 0
    assert orjson.loads(reverted_read.output) == [{"type": "verdict", "body": "repo-b"}]