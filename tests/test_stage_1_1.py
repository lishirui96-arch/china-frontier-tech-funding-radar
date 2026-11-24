from __future__ import annotations

import csv
import io
import json
import sqlite3

import pytest

from funding_radar.classification import classify_document
from funding_radar.dedup import compare_events
from funding_radar.document_service import extract_document, screen_document
from funding_radar.extraction import extract_grounded_fields
from funding_radar.ingestion import ImportItem, canonicalize_url, import_items, parse_csv_bytes
from funding_radar.repository import LedgerRepository, now
from funding_radar.review_service import change_release_status, record_review, update_event_fields
from funding_radar.services import create_release
from tests.conftest import add_company, add_document, add_event, add_required_evidence


def test_canonical_url_removes_tracking_and_fragment():
    assert canonicalize_url("HTTPS://Example.COM/a/?utm_source=x&b=2#top") == "https://example.com/a?b=2"


def test_bulk_import_and_duplicate_tracking(db):
    items=[ImportItem("https://news.example/a?utm_source=x","融资公告","新来源","2025-01-01","完成A轮融资"),ImportItem("https://news.example/a","同文","新来源")]
    result=import_items(items,"tester",db)
    assert result["inserted"]==1 and result["duplicates"]==1
    assert LedgerRepository(db).rows("SELECT COUNT(*) n FROM import_batches")[0]["n"]==1


def test_csv_import_requires_columns_and_parses():
    data="url,title,source_name,published_at,summary\nhttps://example.com/a,标题,来源,2025-01-01,摘要\n".encode()
    assert parse_csv_bytes(data)[0].title=="标题"
    with pytest.raises(ValueError): parse_csv_bytes(b"url,title\nhttps://x,y\n")


@pytest.mark.parametrize("text,expected",[("完成A轮融资","primary_equity"),("获得银行授信","bank_credit"),("启动IPO","ipo"),("获得政府补贴","government_subsidy"),("产品发布会","non_financing")])
def test_document_screening_categories(text,expected):
    assert classify_document(text)[0]==expected


def test_grounded_extraction_has_exact_spans():
    text="公司于今日完成A轮融资，金额为近亿元。"
    rows=extract_grounded_fields(text)
    assert rows and all(text[r["span_start"]:r["span_end"]]==r["raw_value"] for r in rows)


def test_document_screen_and_extract_are_audited(db):
    with __import__('funding_radar.db',fromlist=['connect']).connect(db) as c:
        add_document(c,text="公司完成A轮融资，金额5000万元")
    result=screen_document("doc-1","tester","initial screen",path=db)
    assert result["category"]=="primary_equity"
    assert extract_document("doc-1",db)>=2
    assert LedgerRepository(db).rows("SELECT COUNT(*) n FROM audit_logs")[0]["n"]==1


def test_dedup_computes_investor_and_citation_scores():
    left={"company_id":"c","announcement_date":"2025-01-01","round_normalized":"A","amount_min":10,"amount_max":20,"use_of_funds_original":"中试扩产"}
    right={**left,"announcement_date":"2025-01-03"}
    result=compare_events(left,right,{"i1","i2"},{"i2"},True)
    assert result["investor_score"]==0.5 and result["citation_score"]==1.0


def test_different_round_is_strong_conflict_even_same_company():
    result=compare_events({"company_id":"c","round_normalized":"A"},{"company_id":"c","round_normalized":"B"})
    assert "different_explicit_round" in result["strong_conflicts_json"]


def test_two_independent_review_rounds(db):
    record_review("funding_event","e1",1,"r1","confirmed",{},"first",db)
    record_review("funding_event","e1",2,"r2","needs_correction",{"amount":"dispute"},"second",db)
    rows=LedgerRepository(db).rows("SELECT * FROM review_rounds ORDER BY round_number")
    assert len(rows)==2 and rows[0]["reviewer"]!=rows[1]["reviewer"]


def test_release_status_history_does_not_mutate_release(db):
    from funding_radar.db import connect
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_required_evidence(c)
    rid=create_release("stage11","tester",db)
    before=LedgerRepository(db).rows("SELECT * FROM releases WHERE release_id=?",(rid,))[0]
    change_release_status(rid,"withdrawn","tester","correction",db)
    after=LedgerRepository(db).rows("SELECT * FROM releases WHERE release_id=?",(rid,))[0]
    assert before==after
    assert LedgerRepository(db).rows("SELECT new_status FROM release_status_history WHERE release_id=? ORDER BY changed_at",(rid,))[-1]["new_status"]=="withdrawn"


def test_event_update_rejects_fuzzy_exact_value(db):
    from funding_radar.db import connect
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c)
    with pytest.raises(ValueError):
        update_event_fields("event-1",{"amount_disclosure_type":"bounded_range","amount_exact":100},"tester","bad",db)
