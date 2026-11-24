from __future__ import annotations

from starlette.testclient import TestClient

from funding_radar.db import connect
from funding_radar.public_service import PublicDataService
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
    assert "0亿元" not in home and "0家企业" not in home


def test_public_pages_have_responsive_viewport(monkeypatch, db):
    import public_site.app as site
    monkeypatch.setattr(site, "service", PublicDataService(db))
    html = TestClient(site.app).get("/").text
    assert 'name="viewport"' in html and "/static/site.css" in html
