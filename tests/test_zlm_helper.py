from pathlib import Path

import pytest

from zlm import Zlm


def test_helper_requires_explicit_session_before_append(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        with pytest.raises(ValueError, match="session_id is required"):
            zlm.append("verdict", "hello")


def test_helper_create_session_binds_session_for_append_and_get(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        session_id = zlm.create_session()
        zlm.append("verdict", "hello")

        assert session_id
        assert zlm.get() == [{"type": "verdict", "body": "hello"}]


def test_helper_can_target_existing_session_from_constructor(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        session_id = zlm.create_session()
        zlm.append("verdict", "before")

    with Zlm(db_path=tmp_path / "memory.db", session_id=session_id) as zlm:
        zlm.append("verdict", "after")

        assert zlm.get() == [
            {"type": "verdict", "body": "before"},
            {"type": "verdict", "body": "after"},
        ]


def test_helper_create_session_switches_bound_session(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        first_session = zlm.create_session()
        zlm.append("verdict", "before")
        second_session = zlm.create_session()
        zlm.append("verdict", "after")

        assert first_session != second_session
        assert zlm.get(first_session) == [{"type": "verdict", "body": "before"}]
        assert zlm.get() == [{"type": "verdict", "body": "after"}]


def test_helper_adopt_binds_existing_session(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        session_id = zlm.create_session()
        zlm.append("verdict", "before")

    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        adopted_session_id = zlm.adopt(session_id)
        zlm.append("verdict", "after")

        assert adopted_session_id == session_id
        assert zlm.session_id == session_id
        assert zlm.get() == [
            {"type": "verdict", "body": "before"},
            {"type": "verdict", "body": "after"},
        ]


def test_helper_adopt_rejects_unknown_session(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        with pytest.raises(ValueError, match="unknown session_id"):
            zlm.adopt("missing-session")


def test_helper_get_requires_explicit_or_bound_session(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db") as zlm:
        with pytest.raises(ValueError, match="session_id is required"):
            zlm.get()


def test_helper_allows_configuring_retention_limits(tmp_path: Path) -> None:
    with Zlm(db_path=tmp_path / "memory.db", max_sessions=2, max_entries=2) as zlm:
        first_session = zlm.create_session()
        zlm.append("verdict", "first")

        second_session = zlm.create_session()
        zlm.append("verdict", "second")
        zlm.append("verdict", "second-overflow")
        zlm.append("verdict", "second-latest")

        third_session = zlm.create_session()
        zlm.append("verdict", "third")

        with pytest.raises(ValueError, match="unknown session_id"):
            zlm.get(first_session)

        assert zlm.get(second_session) == [
            {"type": "verdict", "body": "second-overflow"},
            {"type": "verdict", "body": "second-latest"},
        ]
        assert zlm.get() == [{"type": "verdict", "body": "third"}]
        assert zlm.context.list_sessions() == [third_session, second_session]