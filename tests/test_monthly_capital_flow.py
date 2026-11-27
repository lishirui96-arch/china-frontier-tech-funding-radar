from __future__ import annotations

from urllib.parse import urlencode

from starlette.testclient import TestClient

from funding_radar.public_service import PublicDataService, PublicRelease, aggregate_monthly_capital_flow, rolling_window
from public_site.app import app


INDUSTRIES = [
    {"industry_id": "robot", "name": "机器人与具身智能"},
    {"industry_id": "chip", "name": "AI计算与半导体"},
]


def funding(event_id: str, *, currency: str = "CNY", amount: int | None = 100_000_000,
            disclosure: str = "exact", cumulative: bool = False, industry: str = "robot",
            date: str = "2026-11-10", round_name: str = "A") -> dict:
    return {"event_id": event_id, "company_id": "company-" + event_id, "announcement_date": date,
            "round_normalized": round_name, "amount_currency": currency, "amount_exact": amount,
            "amount_disclosure_type": disclosure, "is_cumulative_amount": cumulative,
            "primary_industry_id": industry}


def test_capital_flow_deduplicates_and_keeps_currencies_separate():
    rows = [
        funding("one"), funding("one"),
        funding("two", currency="USD", amount=20_000_000, industry="chip", round_name="B"),
        funding("three", amount=None, disclosure="undisclosed"),
        funding("four", amount=80_000_000, cumulative=True),
        funding("five", amount=None, disclosure="bounded_range"),
    ]
    result = aggregate_monthly_capital_flow(rows, INDUSTRIES, "2026-11", updated_at="2026-11-26")
    assert result["totals"]["event_count"] == 5
    assert result["totals"]["amount_disclosed_event_count"] == 2
    assert result["totals"]["range_amount_event_count"] == 1
    assert result["totals"]["undisclosed_amount_event_count"] == 1
    assert result["totals"]["cumulative_amount_event_count"] == 1
    assert result["totals"]["usd_event_count"] == 1
    assert result["totals"]["amounts"] == {"CNY": 100_000_000, "USD": 20_000_000}
    assert result["totals"]["company_count"] == 5
    assert result["industries"][0]["event_count"] == 4
    assert result["industries"][1]["event_count"] == 1
    assert result["rounds"][0]["amounts"]["CNY"] == 100_000_000
    assert [item["month"] for item in result["trend"]] == ["2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11"]


def test_filters_apply_before_monthly_aggregation():
    rows = [funding("one"), funding("two", currency="USD", amount=10, industry="chip", round_name="B")]
    result = aggregate_monthly_capital_flow(rows, INDUSTRIES, "2026-11", currency="USD", industry_id="chip", round_name="B")
    assert result["totals"]["event_count"] == 1
    assert result["totals"]["amounts"] == {"USD": 10}


def test_rolling_windows_are_inclusive_and_deduplicate_events():
    rows = [funding("one", date="2026-11-25"), funding("one", date="2026-11-25"),
            funding("edge", date="2026-10-27"), funding("old", date="2026-10-26")]
    result = rolling_window(rows, 30)
    assert result["start_date"] == "2026-10-27"
    assert result["end_date"] == "2026-11-25"
    assert {row["event_id"] for row in result["events"]} == {"one", "edge"}


class GateService(PublicDataService):
    def current_release(self):
        return PublicRelease("release", "R", "2026-11-26T00:00:00+08:00", "hash", (
            {"event_id": "ledger-1", "review_item_id": "review-1", "amount_exact": 50_000_000,
             "amount_currency": "CNY", "amount_disclosure_type": "exact"},
            {"event_id": "ledger-2", "amount_exact": 90_000_000, "amount_currency": "CNY",
             "amount_disclosure_type": "exact"},
        ))

    def _rows(self, sql, params=()):
        if "v15_confirmed_funding_events" in sql:
            return [{"confirmed_event_id": "confirmed-1", "review_item_id": "review-1", "company_id": "company-1",
                     "company_name": "测试企业", "disclosure_date": "2026-11-20", "round_original": "A轮",
                     "round_confirmed": "A", "amount_original": "5000万元", "amount_currency": "CNY", "amount_cny": 50_000_000}]
        if "v30_historical_records" in sql:
            return [{"review_item_id": "review-1", "primary_industry_id": "robot", "primary_field_id": "field", "primary_topic_id": "topic"}]
        return []


def test_release_gate_requires_explicit_confirmation_identifier():
    rows, updated = GateService()._strict_formal_events()
    assert updated == "2026-11-26T00:00:00+08:00"
    assert [item["event_id"] for item in rows] == ["confirmed-1"]


def test_public_api_and_home_show_real_empty_state():
    client = TestClient(app)
    response = client.get("/api/monthly-capital-flow?month=2026-11")
    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "formal_confirmed_release_only"
    assert payload["totals"]["event_count"] == 0
    assert payload["totals"]["amounts"] == {}
    assert len(payload["industries"]) == 10
    home = client.get("/").text
    assert "本周期暂无人工确认的正式融资事件" in home
    assert "资本流向：资金由市场流入各产业领域" not in home
    assert "已披露融资金额" in home
    assert "区间披露金额事件" in home
    assert "各领域融资事件次数与占比" in home
    assert "/events?industry_id=" in home
    assert "候选融资事件数" in home and "113 起" in home
    assert "涉及企业数（候选）" in home and "113 家" in home
    assert "近30天融资记录" in home
    assert "共113条，其中113条已归入一级分类" in home
    assert "恒元光电" in home and "乾原量子" in home and "术加医疗" in home
    assert home.count("<tr><td>") >= 113
    assert 'href="/companies/repeated"' in home
    assert "覆盖产业领域数（候选）" in home and "10 个" in home
    assert "近6个月融资趋势" not in home
    assert "VC（Pre-A–B++） 产业领域分布" in home
    assert "占全部候选样本" in home
    assert "round_group=vc" in home and "round_group=early" in home
    repeated = client.get("/companies/repeated")
    assert repeated.status_code == 200
    assert "谱星航天" in repeated.text and "已合并重复来源" in repeated.text
    assert "蓝固新能源" in repeated.text and "保留1个事件" in repeated.text
    assert 'data-period="30"' in home and 'data-period="90"' in home and 'data-period="360"' in home
    assert "数据完整覆盖所选窗口" in home
    assert "window=30" in home and "window=90" in home and "window=360" in home
    assert home.index("资本流向概览") < home.index("产业技术分类导航")
    formal = client.get("/events?scope=formal&industry_id=robot").text
    assert "暂无人工确认的正式融资事件" in formal
    assert "共97条" not in formal


def test_api_rejects_invalid_month():
    response = TestClient(app).get("/api/monthly-capital-flow?month=2026-13")
    assert response.status_code == 422


def test_rolling_capital_api_separates_formal_and_candidate_data():
    client = TestClient(app)
    response = client.get("/api/capital-flow?window=90")
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_days"] == 90
    assert payload["formal_release"]["event_count"] == 0
    assert payload["candidate_observation"]["industries"]["total"] == 378
    assert payload["date_range"]["coverage_complete"] is True
    assert client.get("/api/capital-flow?window=31").status_code == 422


def test_30_day_additions_and_every_bar_drill_down_match():
    service = PublicDataService()
    events = rolling_window(service.historical_candidate_events(), 30, cutoff="2026-11-25")["events"]
    additions = [event for event in events if event["disclosure_date"] <= "2026-11-01"]
    assert len(events) == 113 and len(additions) == 18
    assert {event["company_name_standard"] for event in additions} >= {
        "乾原量子", "恒元光电", "百世达", "脑虎科技", "宜诺生物", "天嗅智能", "术加医疗"
    }

    client = TestClient(app)
    window = service.v30_candidate_window(30)
    for industry in window["industries"]["industries"]:
        response = client.get("/events?" + urlencode({"industry_id": industry["industry_id"], "window": 30}))
        assert response.status_code == 200
        assert response.text.count("<tr><td>") == industry["event_count"]
    for group in window["rounds"]["groups"]:
        for industry in group["industries"]:
            response = client.get("/events?" + urlencode({
                "industry_id": industry["industry_id"], "round_group": group["key"], "window": 30,
            }))
            assert response.status_code == 200
            assert response.text.count("<tr><td>") == industry["event_count"]


def test_same_company_date_and_source_are_merged_into_one_display_event():
    events = PublicDataService().historical_candidate_events()
    yinuo = [event for event in events if event["company_name_standard"] == "宜诺生物"]
    assert len(yinuo) == 1
    assert yinuo[0]["round_original"] == "天使轮 / Pre-A轮"
    assert yinuo[0]["merged_record_count"] == 2
