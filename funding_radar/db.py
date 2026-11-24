from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "funding_radar.db"
FORBIDDEN_MARKERS = ("university-research-radar", "radar.db")


def database_path() -> Path:
    raw = os.environ.get("FUNDING_RADAR_DB_PATH", "").strip()
    path = Path(raw) if raw else DEFAULT_DB_PATH
    resolved = path.resolve()
    lowered = str(resolved).lower()
    if "university-research-radar" in lowered or resolved.name.lower() == "radar.db":
        raise RuntimeError("Refusing to use the original research-radar database path")
    return resolved


def connect(path: Path | None = None, *, read_only: bool = False) -> sqlite3.Connection:
    target = (path or database_path()).resolve()
    if "university-research-radar" in str(target).lower() or target.name.lower() == "radar.db":
        raise RuntimeError("Refusing to access the original research-radar database")
    if read_only:
        connection = sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True, timeout=30)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(target, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


@contextmanager
def transaction(path: Path | None = None):
    connection = connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()

