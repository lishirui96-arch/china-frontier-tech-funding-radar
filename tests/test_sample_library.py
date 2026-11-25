from funding_radar.db import connect
from funding_radar.repository import now
from funding_radar.sample_library import SampleLibraryService


def test_schema_v3_contains_sample_library_tables(db):
    with connect(db) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"sample_event_profiles","acquisition_events","company_technology_profiles","technology_keywords","candidate_themes","candidate_theme_actions"}.issubset(tables)


def test_theme_rename_is_locked_and_audited(db):
    t = now()
    with connect(db) as connection:
        connection.execute("INSERT INTO candidate_themes VALUES (?,?,?,?,?,?,?,'pending',NULL,0,NULL,?,?)", ("theme-1","暂定方向","robotics","核心部件","证据","边界","问题",t,t))
    service = SampleLibraryService(db)
    service.review_theme("theme-1", action="rename", actor="reviewer", reason="人工确认", final_name="机器人触觉与力觉感知")
    with connect(db) as connection:
        theme = connection.execute("SELECT final_name,final_name_locked FROM candidate_themes WHERE theme_id='theme-1'").fetchone()
        actions = connection.execute("SELECT COUNT(*) FROM candidate_theme_actions WHERE theme_id='theme-1'").fetchone()[0]
        audits = connection.execute("SELECT COUNT(*) FROM audit_logs WHERE entity_id='theme-1'").fetchone()[0]
    assert tuple(theme) == ("机器人触觉与力觉感知",1)
    assert actions == audits == 1


def test_unreported_amount_is_not_zero(db):
    with connect(db) as connection:
        row = connection.execute("SELECT normalized_amount_cny FROM sample_event_profiles LIMIT 1").fetchone()
    assert row is None
