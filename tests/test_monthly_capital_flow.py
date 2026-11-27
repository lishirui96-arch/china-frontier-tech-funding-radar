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
    assert len(payload["industries"]) == 11
    home = client.get("/").text
    assert "本周期暂无人工确认的正式融资事件" in home
    assert "资本流向：资金由市场流入各产业领域" not in home
    assert "已披露融资金额" in home
    assert "区间披露金额事件" in home
    assert "各领域融资事件次数与占比" in home
    assert "/events?industry_id=" in home
    assert "候选融资事件数" in home and "116 起" in home
    assert "涉及企业数（候选）" in home and "116 家" in home
    assert "近30天融资记录" in home
    assert "共116条，其中116条已归入一级分类" in home
    assert "英汉思动力" in home and "闪科光联" in home and "华源智因" in home
    assert home.count("<tr><td>") >= 116
    assert 'href="/companies/multiple-fundings?window=30"' in home
    assert "覆盖产业领域数（候选）" in home and "10 个" in home
    assert "近6个月融资趋势" not in home
    assert "VC（Pre-A–B++） 产业领域分布" in home
    assert "占全部候选样本" in home
    assert "round_group=vc" in home and "round_group=early" in home
    repeated = client.get("/companies/repeated")
    assert repeated.status_code == 200
    assert "谱星航天" in repeated.text and "已合并重复来源" in repeated.text
    assert "蓝固新能源" in repeated.text and "保留1个事件" in repeated.text
    multiple = client.get("/companies/multiple-fundings?window=90")
    assert multiple.status_code == 200
    assert "共1家企业" in multiple.text and "元示科技" in multiple.text
    assert "超球面科技" not in multiple.text
    assert multiple.text.count("<tr><td>") == 2
    multiple_360 = client.get("/companies/multiple-fundings?window=360")
    assert multiple_360.status_code == 200
    assert "共117家企业" in multiple_360.text
    assert multiple_360.text.count('窗口内多次融资') == 117
    assert "117 家在期内多次融资" in client.get("/?window=360").text
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
    assert payload["candidate_observation"]["industries"]["total"] == 381
    assert payload["date_range"]["coverage_complete"] is True
    assert client.get("/api/capital-flow?window=31").status_code == 422


def test_90_day_period_link_updates_home_record_table_and_classification():
    client = TestClient(app)
    home = client.get("/?window=90")
    assert home.status_code == 200
    assert 'class="capital-period active" data-period="90"' in home.text
    assert 'data-capital-window="90" >' in home.text
    assert "近90天融资记录" in home.text
    assert "共381条，其中381条已归入一级分类" in home.text
    assert home.text.count("<tr><td>") == 381
    assert "安柏芮ANDPERIOD" in home.text
    assert 'onclick="selectCapitalPeriod(90,this)"' in home.text
    assert "fetch('/api/funding-records?window='+days)" in home.text
    assert "history.replaceState(null,'','/?window='+days)" in home.text

    events = rolling_window(PublicDataService().historical_candidate_events(), 90,
                            cutoff="2026-11-27")["events"]
    andperiod = next(event for event in events if event["company_name_standard"] == "安柏芮ANDPERIOD")
    assert andperiod["classification"] == {
        "primary_industry_id": "d97f43a8-6431-53ab-8a0f-7b249293c6ec",
        "primary_field_id": "edc8b06e-95f5-5d50-bc86-eaa6c90b8398",
        "primary_topic_id": "16e44396-6f2a-5182-8b1e-f5ea08500c80",
    }


def test_funding_records_api_returns_each_window_without_navigation():
    client = TestClient(app)
    for days, total, classified in ((30, 116, 116), (90, 381, 381), (360, 1397, 1397)):
        response = client.get(f"/api/funding-records?window={days}")
        assert response.status_code == 200
        payload = response.json()
        assert payload["window_days"] == days
        assert payload["total"] == total
        assert payload["classified"] == classified
        assert payload["html"].count("<tr><td>") == total
    assert client.get("/api/funding-records?window=31").status_code == 422


def test_360_day_audit_classifies_every_event_and_merges_confirmed_series():
    service = PublicDataService()
    assert service.v30_taxonomy()["version"] == "V3.8"
    events = rolling_window(service.historical_candidate_events(), 360, cutoff="2026-11-27")["events"]
    assert len(events) == 1397
    assert all(event["classification"]["primary_industry_id"] for event in events)

    junhe = [event for event in events if event["company_name_standard"] == "钧合原子"]
    assert len(junhe) == 1
    assert junhe[0]["merged_record_count"] == 2
    assert len(junhe[0]["merged_source_urls"]) == 2
    assert junhe[0]["classification"]["primary_topic_id"] == "3a6de858-d0ef-5a96-8c18-8640e655d4bf"

    photonpay = next(event for event in events if event["company_name_standard"] == "PhotonPay光子易")
    assert photonpay["classification"]["primary_industry_id"] == "ff7843c2-7043-5859-bc3a-7d95cc558acf"


def test_30_day_increment_and_every_bar_drill_down_match():
    service = PublicDataService()
    events = rolling_window(service.historical_candidate_events(), 30, cutoff="2026-11-27")["events"]
    additions = [event for event in events if event["disclosure_date"] >= "2026-11-26"]
    assert len(events) == 116 and len(additions) == 12
    assert {event["company_name_standard"] for event in additions} == {
        "英汉思动力", "博登智能", "零次方机器人", "粒影生物", "时空智子", "向量奇点",
        "环码生物", "迈塔兰斯", "华辰芯光", "华源智因", "HearWell", "闪科光联",
    }
    shanke = next(event for event in additions if event["company_name_standard"] == "闪科光联")
    assert shanke["round_original"] == "种子轮 / 天使轮" and shanke["merged_record_count"] == 2

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


def test_90_day_every_bar_drill_down_matches():
    service = PublicDataService()
    client = TestClient(app)
    window = service.v30_candidate_window(90)
    for industry in window["industries"]["industries"]:
        response = client.get("/events?" + urlencode({"industry_id": industry["industry_id"], "window": 90}))
        assert response.status_code == 200
        assert response.text.count("<tr><td>") == industry["event_count"]
    for group in window["rounds"]["groups"]:
        for industry in group["industries"]:
            response = client.get("/events?" + urlencode({
                "industry_id": industry["industry_id"], "round_group": group["key"], "window": 90,
            }))
            assert response.status_code == 200
            assert response.text.count("<tr><td>") == industry["event_count"]


def test_industry_cards_follow_selected_window_and_link_to_matching_events():
    service = PublicDataService()
    client = TestClient(app)
    home = client.get("/?window=30").text
    assert "function selectIndustryPeriod(days)" in home
    assert "button.addEventListener('click',()=>selectIndustryPeriod(button.dataset.period))" in home

    fintech_id = "ff7843c2-7043-5859-bc3a-7d95cc558acf"
    assert f'data-industry-id="{fintech_id}" data-count-30="0" data-count-90="0" data-count-360="1"' in home
    assert f'href="/events?industry_id={fintech_id}&amp;window=30"' in home

    for days in (30, 90, 360):
        window = service.v30_candidate_window(days)
        for industry in window["industries"]["industries"]:
            response = client.get("/events?" + urlencode({
                "industry_id": industry["industry_id"], "window": days,
            }))
            assert response.status_code == 200
            assert response.text.count("<tr><td>") == industry["event_count"]


def test_global_search_covers_360_day_companies_technology_tracks_and_investors():
    client = TestClient(app)

    company = client.get("/search?q=PhotonPay")
    assert company.status_code == 200
    assert "360-DAY SEARCH" in company.text
    assert "PhotonPay光子易" in company.text
    assert "企业" in company.text and "360天融资事件" in company.text
    assert "/events/c2a7941e-febf-5302-a546-a74303ee2797" in company.text

    technology = client.get("/search?q=跨境支付")
    assert technology.status_code == 200
    assert "PhotonPay光子易" in technology.text

    track = client.get("/search?q=金融科技与数字支付")
    assert track.status_code == 200
    assert "一级赛道" in track.text
    assert "industry_id=ff7843c2-7043-5859-bc3a-7d95cc558acf&amp;window=360" in track.text

    investor = client.get("/search?q=IDG资本")
    assert investor.status_code == 200
    assert "投资机构相关融资" in investor.text and "PhotonPay光子易" in investor.text

    detail = client.get("/events/c2a7941e-febf-5302-a546-a74303ee2797")
    assert detail.status_code == 200
    assert "360-DAY CANDIDATE EVENT" in detail.text and "PhotonPay光子易" in detail.text


def test_same_company_date_and_source_are_merged_into_one_display_event():
    events = PublicDataService().historical_candidate_events()
    yinuo = [event for event in events if event["company_name_standard"] == "宜诺生物"]
    assert len(yinuo) == 1
    assert yinuo[0]["round_original"] == "天使轮 / Pre-A轮"
    assert yinuo[0]["merged_record_count"] == 2


def test_cross_source_duplicate_report_is_merged_but_real_repeat_funding_is_preserved():
    events = PublicDataService().historical_candidate_events()
    hypersphere = [event for event in events if event["company_name_standard"] == "超球面科技"]
    assert len(hypersphere) == 1
    assert hypersphere[0]["merged_record_count"] == 2
    assert len(hypersphere[0]["merged_source_urls"]) == 2
    yuanshi = [event for event in events if event["company_name_standard"] == "元示科技"]
    assert len(yuanshi) == 2
    assert {event["round_original"] for event in yuanshi} == {"天使轮 / 天使+轮", "Pre-A轮"}
