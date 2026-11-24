from __future__ import annotations

import json

from starlette.testclient import TestClient

from funding_radar.db import connect
from funding_radar.public_service import PublicDataService, PublicFilters, china_month
from funding_radar.repository import now
from tests.conftest import add_company, add_document, add_event


def publish_snapshots(db, release_id: str, events: list[dict], created_at: str = "2026-11-01T00:00:00+00:00") -> None:
    with connect(db) as connection:
        connection.execute(
            "INSERT INTO releases VALUES (?,?,?,?,?,?,?,?)",
            (release_id, release_id, "tester", created_at, "{}", len(events), release_id * 4, "published"),
        )
        for position, event in enumerate(events, 1):
            connection.execute(
                "INSERT INTO release_events VALUES (?,?,?,?,?)",
                (release_id, event["event_id"], json.dumps(event, ensure_ascii=False), "[]", position),
            )


def event(event_id: str, date: str | None, track_id: str = "robot", track_name: str = "机器人核心部件", investors: list[dict] | None = None) -> dict:
    return {
        "event_id": event_id,
        "company_id": "company-1",
        "company_name": "测试科技甲",
        "announcement_date": date,
        "round_original": "A轮",
        "round_normalized": "A",
        "amount_original": "5000万元",
        "amount_exact": 50_000_000,
        "amount_disclosure_type": "exact",
        "is_cumulative_amount": 0,
        "primary_track_id": track_id,
        "primary_track_name": track_name,
        "investors": investors or [],
    }


def prepare_event_rows(db, count: int = 4) -> None:
    with connect(db) as connection:
        add_document(connection)
        add_company(connection)
        for index in range(1, count + 1):
            add_event(connection, event_id=f"event-{index}")


def test_china_month_natural_month_cross_year_and_timezone():
    assert china_month("2025-12-31") == "2025-12"
    assert china_month("2026-01-01") == "2026-01"
    assert china_month("2025-12-31T16:30:00Z") == "2026-01"
    assert china_month("2026-01-01T00:30:00+09:00") == "2025-12"
    assert china_month(None) is None
    assert china_month("日期不明确") is None


def test_monthly_counts_and_investor_are_deduplicated(db):
    prepare_event_rows(db, 2)
    investor = {"investor_id": "investor-1", "official_name": "测试创投"}
    events = [
        event("event-1", "2026-01-03", investors=[investor, dict(investor)]),
        event("event-2", "2026-01-20", investors=[investor]),
    ]
    publish_snapshots(db, "release-1", events)
    result = PublicDataService(db).monthly_analysis()
    assert result["months"] == [{"month": "2026-01", "tracks": [{"track_id": "robot", "track_name": "机器人核心部件", "event_count": 2}], "total_event_count": 2}]
    assert result["investors"][0]["investor_event_count"] == 2


def test_multiple_tracks_use_only_explicit_primary_track(db):
    prepare_event_rows(db, 1)
    item = event("event-1", "2026-02-01")
    item.pop("primary_track_id")
    item.pop("primary_track_name")
    item["tracks"] = [
        {"track_id": "robot", "track_name": "机器人", "is_primary": True},
        {"track_id": "ai", "track_name": "人工智能", "is_primary": False},
    ]
    publish_snapshots(db, "release-1", [item])
    result = PublicDataService(db).monthly_analysis()
    assert result["months"][0]["total_event_count"] == 1
    assert result["months"][0]["tracks"] == [{"track_id": "robot", "track_name": "机器人", "event_count": 1}]


def test_month_filter_updates_investors_and_event_table(db):
    prepare_event_rows(db, 2)
    first = {"investor_id": "investor-1", "official_name": "甲机构"}
    second = {"investor_id": "investor-2", "official_name": "乙机构"}
    publish_snapshots(db, "release-1", [event("event-1", "2026-01-02", investors=[first]), event("event-2", "2026-02-02", investors=[second])])
    result = PublicDataService(db).monthly_analysis(PublicFilters(month="2026-02"))
    assert [item["investor_name"] for item in result["investors"]] == ["乙机构"]
    assert [item["event_id"] for item in result["events"]] == ["event-2"]
    assert len(result["months"]) == 2


def test_track_filter_updates_chart_ranking_and_events(db):
    prepare_event_rows(db, 2)
    first = {"investor_id": "investor-1", "official_name": "机器人基金"}
    second = {"investor_id": "investor-2", "official_name": "芯片基金"}
    publish_snapshots(db, "release-1", [event("event-1", "2026-03-02", investors=[first]), event("event-2", "2026-03-03", "chip", "先进封装", [second])])
    result = PublicDataService(db).monthly_analysis(PublicFilters(track_id="chip"))
    assert result["months"][0]["total_event_count"] == 1
    assert [item["investor_name"] for item in result["investors"]] == ["芯片基金"]
    assert [item["event_id"] for item in result["events"]] == ["event-2"]


def test_unknown_dates_and_unverified_gaps_are_not_zero_filled(db):
    prepare_event_rows(db, 3)
    publish_snapshots(db, "release-1", [event("event-1", "2026-01-02"), event("event-2", "2026-03-02"), event("event-3", None)])
    result = PublicDataService(db).monthly_analysis()
    assert [item["month"] for item in result["months"]] == ["2026-01", "2026-03"]
    assert result["coverage"] == {"first_month": "2026-01", "last_month": "2026-03", "complete": False}
    assert result["total_events"] == 2


def test_latest_release_isolated_and_withdrawn_release_hidden(db):
    prepare_event_rows(db, 2)
    publish_snapshots(db, "release-1", [event("event-1", "2026-01-01")], "2026-01-01T00:00:00+00:00")
    publish_snapshots(db, "release-2", [event("event-2", "2026-02-01")], "2026-02-01T00:00:00+00:00")
    service = PublicDataService(db)
    assert [item["month"] for item in service.monthly_analysis()["months"]] == ["2026-02"]
    with connect(db) as connection:
        audit_id = "audit-withdraw"
        connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (audit_id, "tester", "withdraw", "release", "release-2", None, "{}", "test", None, now()))
        connection.execute("INSERT INTO release_status_history VALUES (?,?,?,?,?,?,?,?)", ("status-withdraw", "release-2", "published", "withdrawn", "tester", "test", now(), audit_id))
    assert [item["month"] for item in service.monthly_analysis()["months"]] == ["2026-01"]


def test_empty_monthly_state_has_no_coverage(db):
    result = PublicDataService(db).monthly_analysis()
    assert result["months"] == []
    assert result["investors"] == []
    assert result["coverage"] is None


def test_home_links_month_track_ranking_and_table_filters(monkeypatch, db):
    prepare_event_rows(db, 2)
    first = {"investor_id": "investor-1", "official_name": "机器人基金"}
    second = {"investor_id": "investor-2", "official_name": "芯片基金"}
    publish_snapshots(db, "release-1", [event("event-1", "2026-03-02", investors=[first]), event("event-2", "2026-04-03", "chip", "先进封装", [second])])
    import public_site.app as site

    monkeypatch.setattr(site, "service", PublicDataService(db))
    client = TestClient(site.app)
    home = client.get("/").text
    assert "2026-03" in home and "2026-04" in home
    assert "机器人基金" in home and "芯片基金" in home
    assert "month=2026-03" in home and "track=chip" in home
    month_filtered = client.get("/?month=2026-03").text
    assert "当前月份：2026-03" in month_filtered
    assert "机器人基金" in month_filtered and "芯片基金" not in month_filtered
    track_filtered = client.get("/?track=chip").text
    assert "先进封装" in track_filtered and "芯片基金" in track_filtered
    assert "/companies/company-1" in track_filtered
