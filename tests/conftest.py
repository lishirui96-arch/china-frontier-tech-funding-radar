from __future__ import annotations

import json
from pathlib import Path

import pytest

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "ledger-test.db"
    migrate(path)
    connection = connect(path)
    t = now()
    with connection:
        connection.execute("INSERT INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("src-a", "Fixture official", "company_official", "official", "A", "https://example.invalid", "test-only", t))
        connection.execute("INSERT INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("src-d", "Fixture lead", "aggregator", "aggregator", "D", "https://example.invalid", "test-only", t))
        connection.execute("INSERT INTO amount_rule_versions VALUES (?,?,?,?,?)", ("amount-v1", "1.0.0", json.dumps({"test": True}), 1, t))
        connection.execute("INSERT INTO rule_versions VALUES (?,?,?,?,?,?)", ("dedup-v1", "dedup", "1.0.0", json.dumps({"test": True}), 1, t))
    connection.close()
    return path


def add_document(connection, doc_id="doc-1", grade="A", text="公司宣布完成融资"):
    source = "src-a" if grade != "D" else "src-d"
    connection.execute("""INSERT INTO raw_documents(document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,discovered_via_document_id,archive_status,parser_version,relevance_status,review_status,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (doc_id, source, f"https://example.invalid/{doc_id}", f"https://example.invalid/{doc_id}", "固定脱敏测试文档", "2025-01-01", now(), text, doc_id*4, "fixture", None, "summary_saved", "fixture-v1", "relevant", "field_review", now()))


def add_company(connection, company_id="company-1", name="测试科技甲", status="confirmed"):
    connection.execute("INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (company_id, name, name[:4], None, "中国", "example.invalid", "legal_entity", "confirmed" if status == "confirmed" else "needs_review", status, "doc-1", now(), now()))


def add_event(connection, event_id="event-1", company_id="company-1", grade="A", review="approved", round_norm="A", amount="5000万元", exact=50_000_000, disclosure="exact"):
    cumulative = int(disclosure == "cumulative_only")
    connection.execute("INSERT INTO funding_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (event_id, company_id, "2025-01-01", None, round_norm+"轮" if round_norm else None, round_norm, amount, exact, exact, exact, "CNY", disclosure, "amount-v1", 1.0, cumulative, "研发与中试", "active", grade, review, None, now(), now()))


def add_required_evidence(connection, event_id="event-1", doc_id="doc-1", grade="A"):
    for field, excerpt in [("company_id", "测试科技甲"), ("financing_fact", "宣布完成融资"), ("announcement_date", "2025年1月1日")]:
        connection.execute("INSERT INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (uid(), doc_id, "funding_event", event_id, field, excerpt, 0, len(excerpt), grade, "verified", "tester", now(), now()))

