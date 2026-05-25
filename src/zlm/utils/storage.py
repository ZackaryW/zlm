from __future__ import annotations

import tempfile
import time
from pathlib import Path


_last_ts = 0


def default_db_path() -> Path:
    return Path(tempfile.gettempdir()) / "zlm-memory.db"


def now_ts() -> int:
    global _last_ts

    current_ts = time.time_ns()
    if current_ts <= _last_ts:
        current_ts = _last_ts + 1

    _last_ts = current_ts
    return current_ts