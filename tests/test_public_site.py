from __future__ import annotations

from starlette.testclient import TestClient

from funding_radar.db import connect
from funding_radar.public_service import PublicDataService, candidate_industry_structure, candidate_round_structure, repeated_candidate_companies
from funding_radar.review_service import change_release_status
from funding_radar.services import create_release
from tests.conftest import add_company, add_document, add_event, add_required_evidence


def test_public_service_returns_empty_without_release(db):
    data = PublicDataService(db).overview()
    assert data["release"] is None and data["metrics"] is None and data["events"] == ()


def test_public_service_reads_only_release_snapshot(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c); add_required_evidence(c)
    service = PublicDataService(db)
    assert service.overview()["metrics"] is None
    release_id = create_release("public-v1", "tester", db)
    metrics = service.overview()["metrics"]
    assert metrics == {"events": 1, "exact_amount": 50_000_000, "companies": 1, "investors": 0}
    with connect(db) as c:
        c.execute("UPDATE funding_events SET amount_exact=60000000,amount_min=60000000,amount_max=60000000 WHERE event_id='event-1'")
    assert service.overview()["metrics"]["exact_amount"] == 50_000_000
    change_release_status(release_id, "withdrawn", "tester", "withdraw", db)
    assert service.overview()["metrics"] is None


def test_public_service_never_searches_candidate_data(db):
    with connect(db) as c:
        add_document(c); add_company(c); add_event(c, review="field_review")
    assert PublicDataService(db).search("测试科技") == []


def test_public_routes_and_empty_states(monkeypatch, db):
    import public_site.app as site
    monkeypatch.setattr(site, "service", PublicDataService(db))
    client = TestClient(site.app)
    routes = ["/", "/fields", "/fields/engineering", "/tracks", "/tracks/example", "/emerging", "/companies", "/companies/example", "/investors", "/investors/example", "/events", "/events/example", "/methodology", "/search?q=机器人"]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200
        assert "中国前沿科技融资热点雷达" in response.text
    assert client.get("/favicon.ico").status_code == 204
    home = client.get("/").text
    assert "暂无已发布数据" in home
    assert "每月融资事件数" in home and "最活跃投资方" in home and "融资事件明细" in home
    assert "暂无已发布融资数据" in home and "暂无已发布投资机构数据" in home
    assert "90天" not in home and "360天" not in home and "period=" not in home
    assert "0亿元" not in home and "0家企业" not in home


def test_public_pages_have_responsive_viewport(monkeypatch, db):
    import public_site.app as site
    monkeypatch.setattr(site, "service", PublicDataService(db))
    html = TestClient(site.app).get("/").text
    assert 'name="viewport"' in html and "/static/site.css" in html


def test_candidate_round_structure_groups_and_deduplicates():
    events = [
        {"record_id": "1", "round_original": "天使轮", "queue_class": "A"},
        {"record_id": "2", "round_original": "Seed", "queue_class": "B"},
        {"record_id": "3", "round_original": "Pre-A轮", "queue_class": "A"},
        {"record_id": "4", "round_original": "B++轮", "queue_class": "A"},
        {"record_id": "5", "round_original": "战略投资", "queue_class": "B"},
        {"record_id": "5", "round_original": "战略投资", "queue_class": "B"},
    ]
    result = candidate_round_structure(events)
    assert result["total"] == 5
    assert [group["count"] for group in result["groups"]] == [2, 2, 1, 0]
    assert result["queue_counts"] == {"A": 3, "B": 2}


def test_candidate_industry_structure_counts_unique_records():
    industries = [{"industry_id": "robot", "name": "机器人"}, {"industry_id": "ai", "name": "AI计算"}]
    events = [
        {"record_id": "1", "classification": {"primary_industry_id": "robot"}},
        {"record_id": "1", "classification": {"primary_industry_id": "robot"}},
        {"record_id": "2", "classification": {"primary_industry_id": "robot"}},
        {"record_id": "3", "classification": {"primary_industry_id": "ai"}},
    ]
    result = candidate_industry_structure(events, industries)
    assert result["total"] == 3 and result["classified"] == 3 and result["unclassified"] == 0
    assert result["company_count"] == 0 and result["industry_count"] == 2
    assert [(row["industry_id"], row["event_count"]) for row in result["industries"]] == [("robot", 2), ("ai", 1)]


def test_repeated_candidate_companies_distinguishes_rounds_and_sources():
    events = [
        {"record_id": "1", "company_id": "a", "company_name_standard": "甲", "source_platform": "媒体一", "disclosure_date": "2026-11-01", "round_original": "Pre-A", "amount_original": "合计1亿元"},
        {"record_id": "2", "company_id": "a", "company_name_standard": "甲", "source_platform": "媒体一", "disclosure_date": "2026-11-01", "round_original": "A", "amount_original": "合计1亿元"},
        {"record_id": "3", "company_id": "b", "company_name_standard": "乙", "source_platform": "媒体一", "disclosure_date": "2026-11-02", "round_original": "B", "amount_original": "近2亿元"},
        {"record_id": "4", "company_id": "b", "company_name_standard": "乙", "source_platform": "媒体二", "disclosure_date": "2026-11-03", "round_original": "B+", "amount_original": "近2亿元"},
    ]
    result = repeated_candidate_companies(events)
    assert {row["company_name"]: row["finding"] for row in result} == {"甲": "明确多轮融资", "乙": "疑似重复来源"}
