from __future__ import annotations

import tempfile
import time
from pathlib import Path


def default_db_path() -> Path:
    return Path(tempfile.gettempdir()) / "zlm-memory.db"


def now_ts() -> int:
    return time.time_ns()