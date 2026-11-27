from __future__ import annotations

from datetime import date

import scripts.backfill_v35_historical as backfill
from funding_radar.db import connect
from scripts.backfill_v35_historical import ArchiveItem, classify, company_from_title, normalize_round, screen


def test_screen_accepts_target_technology_round():
    item = ArchiveItem("2026-09-01", "某芯片公司完成亿元A轮融资", "https://example.com/1")
    status, _, rounds = screen(item, "公司研发先进封装芯片，本轮由某资本领投。", None)
    assert status == "candidate"
    assert rounds == ["A轮"]


def test_screen_rejects_consumer_and_non_target_round():
    item = ArchiveItem("2026-09-01", "某茶饮品牌完成C轮融资", "https://example.com/2")
    status, reason, rounds = screen(item, "公司经营连锁门店与餐饮零售。", None)
    assert status == "excluded"
    assert "非目标轮次" in reason
    assert rounds == []


def test_screen_rejects_strategic_and_c_subrounds():
    strategic = ArchiveItem("2026-09-01", "某芯片公司完成B+轮战略融资", "https://example.com/s")
    c_round = ArchiveItem("2026-09-01", "某芯片公司完成C1轮融资", "https://example.com/c")
    body = "公司研发先进封装芯片，历史上曾完成A轮融资。"
    assert screen(strategic, body, None)[0] == "excluded"
    assert screen(c_round, body, None)[0] == "excluded"


def test_screen_keeps_unreported_round_for_verification():
    item = ArchiveItem("2026-09-01", "某机器人公司完成新一轮融资", "https://example.com/3")
    status, _, rounds = screen(item, "公司研发人形机器人和灵巧手。", None)
    assert status == "needs_verification"
    assert rounds == ["轮次待核验"]


def test_historical_round_in_body_does_not_override_pending_title():
    item = ArchiveItem("2026-09-01", "某芯片公司完成新一轮融资", "https://example.com/h")
    status, _, rounds = screen(item, "公司研发芯片，此前完成A轮融资。", None)
    assert status == "needs_verification"
    assert rounds == ["轮次待核验"]


def test_classification_prefers_title_and_does_not_force_weak_signal():
    assert classify("量子计算企业完成A轮融资", "公司研发超导量子计算机")[1] == "量子科技"
    assert classify("某科技公司完成A轮融资", "正文仅有一次量子相关旁注")[0] == "pending_judgment"


def test_normalization_and_company_parsing():
    assert normalize_round("pre－A轮") == "Pre-A轮"
    assert company_from_title("星河科技完成数千万元A轮融资") == "星河科技"
    assert company_from_title("创始团队来自上海交大，量感智能完成天使轮融资") == "量感智能"
    assert company_from_title("首发| 聚焦机器人，「灵巧科技」完成A轮融资") == "灵巧科技"
    assert company_from_title("拿下行业首笔亿元级融资，擎天租完成天使轮、天使+轮融资") == "擎天租"


def test_insert_month_is_idempotent(db, monkeypatch):
    monkeypatch.setattr(backfill, "connect", lambda: connect(db))
    item = ArchiveItem("2026-09-01", "星河科技完成数千万元A轮融资", "https://example.com/4")
    article = "星河科技研发先进封装芯片，完成数千万元A轮融资，由某资本领投。"

    first = backfill.insert_month(date(2026, 9, 1), date(2026, 9, 1), [item], {item.url: (article, None)})
    second = backfill.insert_month(date(2026, 9, 1), date(2026, 9, 1), [item], {item.url: (article, None)})

    assert first["events"] == second["events"] == 1
    with connect(db, read_only=True) as connection:
        assert connection.execute("SELECT COUNT(*) FROM v35_collection_batches").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM v35_historical_candidates").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM v35_candidate_sources").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM v35_classification_proposals").fetchone()[0] == 1
