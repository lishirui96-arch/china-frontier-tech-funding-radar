from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from funding_radar.db import connect


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def migrate(path: Path | None = None) -> int:
    connection = connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)")
        applied = {row[0]: row[1] for row in connection.execute("SELECT version, checksum FROM schema_migrations")}
        for file in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(file.name.split("_", 1)[0])
            sql = file.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode()).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(f"Migration {version} checksum changed")
                continue
            applied_at = datetime.now(timezone.utc).isoformat()
            migration_row = ",".join(
                "'" + str(value).replace("'", "''") + "'"
                for value in (version, file.stem, checksum, applied_at)
            )
            try:
                connection.executescript(
                    f"BEGIN IMMEDIATE;\n{sql}\n"
                    f"INSERT INTO schema_migrations VALUES ({migration_row});\nCOMMIT;"
                )
            except sqlite3.Error:
                if connection.in_transaction:
                    connection.rollback()
                raise
        return max(applied.keys() | {int(p.name[:3]) for p in MIGRATIONS_DIR.glob('[0-9][0-9][0-9]_*.sql')}, default=0)
    finally:
        connection.close()

