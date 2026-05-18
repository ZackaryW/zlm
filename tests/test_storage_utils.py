from pathlib import Path
import tempfile

from zlm.utils.storage import default_db_path, now_ts


def test_default_db_path_uses_temp_directory() -> None:
    assert default_db_path() == Path(tempfile.gettempdir()) / "zlm-memory.db"


def test_default_db_path_has_expected_filename() -> None:
    assert default_db_path().name == "zlm-memory.db"


def test_now_ts_returns_integer_nanoseconds() -> None:
    first = now_ts()
    second = now_ts()

    assert isinstance(first, int)
    assert second >= first


def test_now_ts_is_large_enough_to_be_nanosecond_epoch() -> None:
    assert now_ts() > 10**18