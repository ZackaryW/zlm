from pathlib import Path

import orjson
from click.testing import CliRunner

from zlm import main


def test_cli_stress_integration_across_explicit_sessions(tmp_path: Path) -> None:
    runner = CliRunner()
    db_path = tmp_path / "memory.db"

    first_session = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()
    second_session = runner.invoke(main, ["--db-path", str(db_path), "create-session"]).output.strip()

    for value in range(120):
        append_result = runner.invoke(
            main,
            ["--db-path", str(db_path), "append", first_session, "score", str(value)],
        )
        assert append_result.exit_code == 0

    first_read = runner.invoke(main, ["--db-path", str(db_path), "get", first_session])

    assert first_read.exit_code == 0
    assert orjson.loads(first_read.output) == [
        {"type": "score", "body": value}
        for value in range(105, 120)
    ]

    append_second = runner.invoke(
        main,
        ["--db-path", str(db_path), "append", second_session, "verdict", '"after-create-session"'],
    )
    second_read = runner.invoke(main, ["--db-path", str(db_path), "get", second_session])
    first_read_again = runner.invoke(main, ["--db-path", str(db_path), "get", first_session])

    assert append_second.exit_code == 0
    assert second_read.exit_code == 0
    assert first_read_again.exit_code == 0
    assert orjson.loads(second_read.output) == [{"type": "verdict", "body": "after-create-session"}]
    assert orjson.loads(first_read_again.output) == [
        {"type": "score", "body": value}
        for value in range(105, 120)
    ]