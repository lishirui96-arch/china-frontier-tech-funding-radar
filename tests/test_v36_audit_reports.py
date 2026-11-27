from __future__ import annotations

from scripts.write_v36_audit_reports import cluster_event, pending_round_reason


def event(title: str, intro: str = "") -> dict:
    return {"source_title": title, "primary_business": intro, "core_technology": intro}


def test_cluster_uses_direct_title_signal():
    result = cluster_event(event("某企业完成融资，聚焦核聚变工程化"))
    assert result["category"] == "B"
    assert "核能工程" in result["cluster"]


def test_cluster_does_not_force_single_body_keyword():
    result = cluster_event(event("某企业完成A轮融资", "公司介绍中只出现一次芯片。"))
    assert result["category"] == "D"


def test_pending_round_reason_is_reproducible():
    assert pending_round_reason("某企业完成新一轮融资") == "标题仅称新一轮融资"
    assert pending_round_reason("某企业完成首轮融资") == "标题仅称首轮融资"
