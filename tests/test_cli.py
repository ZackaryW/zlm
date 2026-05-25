import orjson
from click.testing import CliRunner

from zlm import main


def test_cli_help_displays_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "append" in result.output
    assert "create-session" in result.output
    assert "get" in result.output
    assert "adopt" not in result.output
    assert "swap" not in result.output


def test_cli_append_help_displays_helper_text() -> None:
    runner = CliRunner()

    result = runner.invoke(main, ["append", "--help"])

    assert result.exit_code == 0
    assert "Append an entry to a session." in result.output
    assert "ZLM_SESSION_ID" in result.output
    assert "$zlmk" in result.output
    assert "[ARGS]..." in result.output


def test_cli_create_session_returns_a_session_id(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    result = runner.invoke(main, ["--db-path", str(db_path), "create-session"])

    assert result.exit_code == 0
    assert result.output.strip()


def test_cli_create_session_can_emit_powershell_env_assignment(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    result = runner.invoke(main, ["--db-path", str(db_path), "create-session", "--export"])

    assert result.exit_code == 0
    assert result.output.startswith("$env:ZLM_SESSION_ID = '")
    assert result.output.strip().endswith("'")


def test_cli_append_and_get_require_explicit_session_id(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    append_result = runner.invoke(main, ["--db-path", str(db_path), "append", "only-session-id"])
    get_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code != 0
    assert get_result.exit_code != 0
    assert "append expects SESSION_ID ENTRY_TYPE BODY_JSON" in append_result.output
    assert "session_id is required; pass SESSION_ID or set ZLM_SESSION_ID" in get_result.output


def test_cli_append_and_get_use_env_session_id_when_present(tmp_path, monkeypatch) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    session_id = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()
    monkeypatch.setenv("ZLM_SESSION_ID", session_id)

    append_result = runner.invoke(main, ["--db-path", str(db_path), "append", "verdict", '"retry"'])
    get_result = runner.invoke(main, ["--db-path", str(db_path), "get"])

    assert append_result.exit_code == 0
    assert get_result.exit_code == 0
    assert orjson.loads(get_result.output) == [{"type": "verdict", "body": "retry"}]


def test_cli_can_append_and_read_session_with_explicit_session_id(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    create_result = runner.invoke(main, ["--db-path", str(db_path), "create-session"])
    session_id = create_result.output.strip()
    append_result = runner.invoke(
        main,
        [
            "--db-path",
            str(db_path),
            "append",
            session_id,
            "decision",
            '{"mode":"fallback","reason":"timeout"}',
        ],
    )

    read_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "get", session_id],
    )

    assert create_result.exit_code == 0
    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert read_result.output == (
        '[\n'
        '{"type":"decision","body":{"mode":"fallback","reason":"timeout"}}\n'
        ']\n'
    )
    assert orjson.loads(read_result.output) == [
        {"type": "decision", "body": {"mode": "fallback", "reason": "timeout"}}
    ]


def test_cli_append_supports_raw_string_body(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    session_id = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()

    append_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", session_id, "verdict", "hello"],
    )
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get", session_id])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "verdict", "body": "hello"}]


def test_cli_append_unwraps_reserved_scalar_key(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    session_id = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()

    append_result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", session_id, "score", '{"$zlmk":1}'],
    )
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get", session_id])

    assert append_result.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [{"type": "score", "body": 1}]


def test_cli_reports_invalid_structured_json_body(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    session_id = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()

    result = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", session_id, "decision", '{"broken":'],
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


def test_cli_append_reuses_explicit_session(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"
    session_id = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()

    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", session_id, "verdict", '"retry"'])
    second_append = runner.invoke(main, ["--db-path", str(db_path), "append", session_id, "flag", "true"])
    read_result = runner.invoke(main, ["--db-path", str(db_path), "get", session_id])

    assert first_append.exit_code == 0
    assert second_append.exit_code == 0
    assert read_result.exit_code == 0
    assert orjson.loads(read_result.output) == [
        {"type": "verdict", "body": "retry"},
        {"type": "flag", "body": True},
    ]


def test_cli_allows_configuring_retention_limits(tmp_path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    first_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "create-session"],
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
            first_session,
            "verdict",
            '"first"',
        ],
    )

    second_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "create-session"],
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
            second_session,
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
            second_session,
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
            second_session,
            "verdict",
            '"second-latest"',
        ],
    )

    third_swap = runner.invoke(
        main,
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "create-session"],
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
            third_session,
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
        ["--db-path", str(db_path), "--max-sessions", "2", "--max-entries", "2", "get", third_session],
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
    monkeypatch.setenv("ZLM_MAX_SESSIONS", "2")
    monkeypatch.setenv("ZLM_MAX_ENTRIES", "2")

    first_swap = runner.invoke(main, ["--db-path", str(db_path), "create-session"])
    first_session = first_swap.output.strip()
    first_append = runner.invoke(main, ["--db-path", str(db_path), "append", first_session, "verdict", '"first"'])

    second_swap = runner.invoke(main, ["--db-path", str(db_path), "create-session"])
    second_session = second_swap.output.strip()
    second_append = runner.invoke(main, ["--db-path", str(db_path), "append", second_session, "verdict", '"second"'])
    second_overflow = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", second_session, "verdict", '"second-overflow"'],
    )
    second_latest = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", second_session, "verdict", '"second-latest"'],
    )

    third_swap = runner.invoke(main, ["--db-path", str(db_path), "create-session"])
    third_session = third_swap.output.strip()
    third_append = runner.invoke(main, ["--db-path", str(db_path), "append", third_session, "verdict", '"third"'])

    evicted_result = runner.invoke(main, ["--db-path", str(db_path), "get", first_session])
    second_result = runner.invoke(main, ["--db-path", str(db_path), "get", second_session])
    current_result = runner.invoke(main, ["--db-path", str(db_path), "get", third_session])

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