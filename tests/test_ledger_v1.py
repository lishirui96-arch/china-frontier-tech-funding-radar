from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from funding_radar.amounts import parse_amount
from funding_radar.db import connect
from funding_radar.dedup import compare_events
from funding_radar.migrations import migrate
from funding_radar.repository import LedgerRepository, now
from funding_radar.services import create_release, decide_dedup, quality_issues
from tests.conftest import add_company, add_document, add_event, add_required_evidence


def test_empty_database_migrates_to_latest(db):
    assert migrate(db) == 13
    with connect(db) as c:
        assert c.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 13


def test_migration_is_idempotent(db):
    migrate(db); migrate(db)
    with connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 13
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='source_audit_runs'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v12_funding_candidates'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v13_candidate_quality_audits'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v14_event_units'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v15_funding_review_queue'").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='v151_source_scope_checks'").fetchone()[0] == 1


def test_foreign_keys_and_checks_enabled(db):
    with pytest.raises(sqlite3.IntegrityError), connect(db) as c:
        c.execute("INSERT INTO company_aliases VALUES ('x','missing','别名','short',NULL,1,'pending',?)", (now(),))


@pytest.mark.parametrize("raw,kind,minv,maxv", [
    ("数千万元", "bounded_range", 20_000_000, 90_000_000),
    ("近亿元", "upper_bound", 80_000_000, 99_999_999),
    ("超亿元", "lower_bound", 100_000_000, None),
    ("逾2亿元", "lower_bound", 200_000_000, None),
    ("数亿元", "bounded_range", 200_000_000, 900_000_000),
    ("亿元级融资", "order_of_magnitude", 100_000_000, 999_999_999),
    ("完成亿元融资", "order_of_magnitude", 100_000_000, 999_999_999),
])
def test_fuzzy_amounts_never_become_exact(raw, kind, minv, maxv):
    result = parse_amount(raw)
    assert result.exact is None and result.disclosure_type == kind
    assert result.minimum == minv and result.maximum == maxv


@pytest.mark.parametrize("raw,currency,exact", [("5000万元人民币","CNY",50_000_000),("5000万美元","USD",50_000_000),("5000万欧元","EUR",50_000_000)])
def test_exact_multicurrency(raw, currency, exact):
    result = parse_amount(raw)
    assert (result.currency, result.exact, result.disclosure_type) == (currency, exact, "exact")


def test_cumulative_never_enters_round_amount():
    result = parse_amount("本轮完成融资，累计融资超5亿元")
    assert result.cumulative and result.exact is None and result.disclosure_type == "cumulative_only"


def test_undisclosed_amount():
    assert parse_amount("金额未披露").disclosure_type == "undisclosed"


def test_aliases_support_chinese_english_and_evidence(db):
    with connect(db) as c:
        add_document(c); add_company(c)
        c.execute("INSERT INTO company_aliases VALUES (?,?,?,?,?,?,?,?)", ("alias-1","company-1","Test Tech","english","doc-1",0.95,"confirmed",now()))
    rows = LedgerRepository(db).list_aliases("companies")
    assert rows[0]["alias"] == "Test Tech" and rows[0]["official_name"] == "测试科技甲"


def test_same_name_different_entities_not_auto_merged(db):
    with connect(db) as c:
        add_document(c); add_company(c, "company-1", "同名科技")
        add_company(c, "company-2", "同名科技")
    result = compare_events({"company_id":"company-1"}, {"company_id":"company-2"})
    assert result["company_score"] == 0 and "different_company" in result["strong_conflicts_json"]


def test_same_event_multiple_documents_counts_once(db):
    with connect(db) as c:
        add_document(c); add_document(c, "doc-2"); add_company(c); add_event(c)
        c.execute("INSERT INTO event_documents VALUES (?,?,?,?,?)", ("event-1","doc-1","primary",1,now()))
        c.execute("INSERT INTO event_documents VALUES (?,?,?,?,?)", ("event-1","doc-2","duplicate_report",1,now()))
    with connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM event_documents").fetchone()[0] == 2


def test_supplemental_disclosure_does_not_add_event(db):
    with connect(db) as c:
        add_document(c); add_document(c,"doc-2"); add_company(c); add_event(c)
        c.execute("INSERT INTO event_documents VALUES (?,?,?,?,?)", ("event-1","doc-2","supporting",1,now()))
    with connect(db) as c:
        assert c.execute("SELECT COUNT(*) FROM funding_events").fetchone()[0] == 1


def test_different_rounds_are_conflict():
    result = compare_events({"company_id":"c","round_normalized":"A","announcement_date":"2025-01-01"}, {"company_id":"c","round_normalized":"B","announcement_date":"2025-01-02"})
    assert "different_explicit_round" in result["strong_conflicts_json"]


def test_dedup_decision_can_be_reversed(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_event(c,"event-2")
        c.execute("INSERT INTO dedup_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("cand-1","event-1","event-2","dedup-v1",1,1,1,1,0,0,0,"[]","{}",0.8,"high","pending",now()))
    first = decide_dedup("cand-1","merge","同一事件","tester","dedup-v1",db)
    second = decide_dedup("cand-1","do_not_merge","发现为追加轮","tester","dedup-v1",db)
    with connect(db) as c:
        current = c.execute("SELECT * FROM dedup_decisions WHERE is_current=1").fetchone()
        assert current["decision_id"] == second and current["reverses_decision_id"] == first


def test_all_published_fields_drill_to_evidence(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_required_evidence(c)
    assert quality_issues(db) == []


def test_unresolved_high_risk_dedup_blocks_release(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_event(c,"event-2"); add_required_evidence(c)
        add_required_evidence(c,"event-2")
        c.execute("INSERT INTO dedup_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("cand-1","event-1","event-2","dedup-v1",1,1,1,1,0,0,0,"[]","{}",0.8,"high","pending",now()))
    with pytest.raises(ValueError, match="高风险"):
        create_release("blocked","tester",db)


def test_d_grade_only_blocks_release(db):
    with connect(db) as c:
        add_document(c,"doc-1","D"); add_company(c); add_event(c,grade="D"); add_required_evidence(c,grade="D")
    assert any("只有 D 级证据" in issue for issue in quality_issues(db))


def test_release_is_immutable_and_reproducible(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_required_evidence(c)
    rid = create_release("r1","tester",db)
    repo = LedgerRepository(db, read_only=True)
    release = repo.rows("SELECT * FROM releases WHERE release_id=?", (rid,))[0]
    manifest = json.loads(release["manifest_json"])
    assert manifest["content_hash"] == release["content_hash"]
    with pytest.raises(sqlite3.IntegrityError), connect(db) as c:
        c.execute("UPDATE releases SET event_count=2 WHERE release_id=?", (rid,))


def test_original_research_database_path_is_rejected():
    bad = Path("C:/tmp/university-research-radar/persistent/data/radar.db")
    with pytest.raises(RuntimeError, match="original research-radar"):
        connect(bad)


def test_repository_read_only_rejects_writes(db):
    with pytest.raises(RuntimeError, match="read-only"):
        LedgerRepository(db, read_only=True).execute("DELETE FROM sources")


def test_logs_and_project_files_contain_no_api_keys():
    import re
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*"):
        if path.is_file() and path.name != Path(__file__).name and ".venv" not in path.parts and path.suffix in {".py",".md",".toml",".sql",".txt",".json"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not re.search(r"\b" + "s" + r"k-[A-Za-z0-9_-]{20,}", text)
            assert not re.search(("OPENALEX" + "_API_KEY") + r"\s*=\s*[^\s'\"]+", text)

