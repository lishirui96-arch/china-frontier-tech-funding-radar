from __future__ import annotations

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.public_service import PublicDataService


def test_schema22_preserves_v32_and_activates_v37(db):
    migrate(db)
    with connect(db, read_only=True) as connection:
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 23
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v37_candidate_classifications'"
        ).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_public_taxonomy_falls_back_when_empty_database_has_no_v32_snapshot(db):
    taxonomy = PublicDataService(db).v30_taxonomy()
    assert taxonomy == {"version": None, "industries": [], "fields": [], "topics": []}


def test_historical_candidate_window_uses_one_shared_cutoff(db):
    service = PublicDataService(db)
    for days in (30, 90, 360):
        result = service.v30_candidate_window(days)
        assert result["end_date"] == "2026-11-27"
        assert result["rounds"]["total"] == 0
