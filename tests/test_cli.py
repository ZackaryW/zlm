import orjson
from click.testing import CliRunner

from zlm import main


def test_cli_help_displays_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "append" in result.output
    assert "adopt" in result.output
    assert "get" in result.output
    assert "swap" in result.output
    assert "create-session" not in result.output
    assert "list-sessions" not in result.output
    assert "latest-session" not in result.output


def test_cli_append_help_displays_helper_text() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["append", "--help"])

    assert result.exit_code == 0
    assert "Append an entry to the current workspace session." in result.output
    assert "$zlmk" in result.output
    assert "ENTRY_TYPE" in result.output
    assert "BODY_JSON" in result.output


def test_cli_adopt_outputs_powershell_env_assignment_for_repo_root(tmp_path) -> None:
    runner = CliRunner()
    repo_root = tmp_path / "repo"
    nested_dir = repo_root / "pkg" / "feature"
    nested_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    result = runner.invoke(main, ["adopt", str(nested_dir)])

    assert result.exit_code == 0
    assert result.output.strip() == f"$env:zlm_cwd_override = '{repo_root.resolve()}'"


def test_cli_env_override_inherits_session_from_other_workspace_path(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    repo_root = tmp_path / "repo"
    source_dir = repo_root / "pkg" / "a"
    unrelated_dir = tmp_path / "other"
    source_dir.mkdir(parents=True)
    unrelated_dir.mkdir()
    (repo_root / ".git").mkdir()

    monkeypatch.chdir(source_dir)
    append_result = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"retry"'])

    monkeypatch.chdir(unrelated_dir)
    monkeypatch.setenv("zlm_cwd_override", str(source_dir))
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "retry"}]


def test_cli_swap_creates_new_current_session(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"retry"'])
    swap_result = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    current_result = runner.invoke(main, ["--db-path", str(db_path), "get"])
    prior_result = runner.invoke(main, ["--db-path", str(db_path), "get", swap_result.output.strip()])

    assert first_append.exit_code == 0
    assert swap_result.exit_code == 0
    assert swap_result.output.strip()
    assert current_result.exit_code == 0
    assert current_result.output == "[]\n"
    assert prior_result.exit_code == 0
    assert orjson.loads(prior_result.output) == []


def test_cli_swap_makes_subsequent_appends_use_new_session(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"before"'])
    first_current = runner.invoke(main, ["--db-path", str(db_path), "get"])
    swap_result = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    second_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"after"'])
    second_current = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert first_append.exit_code == 0
    assert first_current.exit_code == 0
    assert swap_result.exit_code == 0
    assert second_append.exit_code == 0
    assert second_current.exit_code == 0
    assert orjson.loads(first_current.output) == [{"type": "verdict", "body": "before"}]
    assert orjson.loads(second_current.output) == [{"type": "verdict", "body": "after"}]


def test_cli_can_append_and_read_session_without_explicit_session(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    append_result = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "append",
            "decision",
            '{"mode":"fallback","reason":"timeout"}',
        ],
    )

    assert append_result.exit_code == 0

    read_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "get"],
    )

    assert read_result.exit_code == 0
    assert read_result.output == (
        '[\n'
        '{"type":"decision","body":{"mode":"fallback","reason":"timeout"}}\n'
        ']\n'
    )
    assert orjson.loads(read_result.output) == [
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}}
    ]


def test_cli_append_reuses_current_workspace_session(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"retry"'])
    second_append = runner.invoke(main, ["--db-path", str(db_path), "append", "flag", "true"])
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert first_append.exit_code == 0
    assert second_append.exit_code == 0
    assert read_result.exit_code == 0
    assert read_result.output == (
        '[\n'
        '{"type":"verdict","body":"retry"},\n'
        '{"type":"flag","body":true}\n'
        ']\n'
    )
    assert orjson.loads(read_result.output) == [
        {"type": "verdict", "body": "retry"},
        {"type": "flag", "body": True},
    ]


def test_cli_append_supports_raw_string_body(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    append_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "verdict", "hello"],
    )
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "hello"}]


def test_cli_append_unwraps_reserved_scalar_key(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    append_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "score", '{"$zlmk":1}'],
    )
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "score", "body": 1}]


def test_cli_reports_invalid_structured_json_body(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "decision", '{"broken":'],
    )

    assert result.exit_code != 0
    assert "body must be valid JSON" in result.output


def test_cli_reports_unknown_session(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    result = runner.invoke(
        main,
        ["--db-path", str(db_path), "get", "missing-session"],
    )

    assert result.exit_code != 0
    assert "unknown session_id" in result.output


def test_cli_supports_workspace_override(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    append_result = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--workspace-hash",
            "workspace-a",
            "append",
            "verdict",
            '"retry"',
        ],
    )
    read_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "--workspace-hash", "workspace-a", "get"],
    )

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "retry"}]


def test_cli_uses_git_root_as_workspace_basis_across_subdirectories(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    repo_root = tmp_path / "repo"
    first_dir = repo_root / "packages" / "a"
    second_dir = repo_root / "packages" / "b"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)
    (repo_root / ".git").mkdir()

    monkeypatch.chdir(first_dir)
    append_result = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"retry"'])

    monkeypatch.chdir(second_dir)
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "retry"}]


def test_cli_get_session_memory_resolves_latest_session_from_current_workspace(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    append_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "verdict", '"retry"'],
    )
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "retry"}]


def test_cli_get_session_memory_without_session_reports_missing_workspace_session(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert result.exit_code != 0
    assert "no session found for current workspace" in result.output


def test_cli_allows_configuring_retention_limits(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)

    first_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "swap"],
    )
    first_session = first_swap.output.strip()
    first_append = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "append",
            "verdict",
            '"first"',
        ],
    )

    second_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "swap"],
    )
    second_session = second_swap.output.strip()
    second_append = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "append",
            "verdict",
            '"second"',
        ],
    )
    second_overflow = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "append",
            "verdict",
            '"second-overflow"',
        ],
    )
    second_latest = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "append",
            "verdict",
            '"second-latest"',
        ],
    )

    third_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "swap"],
    )
    third_session = third_swap.output.strip()
    third_append = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "append",
            "verdict",
            '"third"',
        ],
    )

    evicted_result = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "get",
            first_session,
        ],
    )
    second_result = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "--max-sessions",
            "2",
            "--max-entries",
            "2",
            "get",
            second_session,
        ],
    )
    current_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "get"],
    )

    assert first_swap.exit_code == 0
    assert first_append.exit_code == 0
    assert second_swap.exit_code == 0
    assert second_append.exit_code == 0
    assert second_overflow.exit_code == 0
    assert second_latest.exit_code == 0
    assert third_swap.exit_code == 0
    assert third_append.exit_code == 0
    assert third_session
    assert evicted_result.exit_code != 0
    assert "unknown session_id" in evicted_result.output
    assert orjson.loads(second_result.output) == [
        {"type": "verdict", "body": "second-overflow"},
        {"type": "verdict", "body": "second-latest"},
    ]
    assert orjson.loads(current_result.output) == [{"type": "verdict", "body": "third"}]


def test_cli_allows_configuring_retention_limits_via_environment(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ZLM_MAX_SESSIONS", "2")
    monkeypatch.setenv("ZLM_MAX_ENTRIES", "2")

    first_swap = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    first_session = first_swap.output.strip()
    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"first"'])

    second_swap = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    second_session = second_swap.output.strip()
    second_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"second"'])
    second_overflow = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "verdict", '"second-overflow"'],
    )
    second_latest = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", "verdict", '"second-latest"'],
    )

    third_swap = runner.invoke(main, ["--db-path", str(db_path), "swap"])
    third_append = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"third"'])

    evicted_result = runner.invoke(main, ["--db-path", str(db_path), "get", first_session])
    second_result = runner.invoke(main, ["--db-path", str(db_path), "get", second_session])
    current_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert first_swap.exit_code == 0
    assert first_append.exit_code == 0
    assert second_swap.exit_code == 0
    assert second_append.exit_code == 0
    assert second_overflow.exit_code == 0
    assert second_latest.exit_code == 0
    assert third_swap.exit_code == 0
    assert third_append.exit_code == 0
    assert evicted_result.exit_code != 0
    assert "unknown session_id" in evicted_result.output
    assert orjson.loads(second_result.output) == [
        {"type": "verdict", "body": "second-overflow"},
        {"type": "verdict", "body": "second-latest"},
    ]
    assert orjson.loads(current_result.output) == [{"type": "verdict", "body": "third"}]