from __future__ import annotations

import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from funding_radar.db import connect
from funding_radar.public_service import rolling_window


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def write_csv(name: str, rows: list[dict]) -> None:
    path = DOCS / name
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def all_days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main() -> None:
    with connect(read_only=True) as connection:
        batches = [dict(row) for row in connection.execute(
            """SELECT period_start,period_end,raw_source_count,new_candidate_count,
                      vc_event_count,early_event_count,pending_round_count,duplicate_source_count,
                      pending_classification_count,status
               FROM v35_collection_batches WHERE created_by='v35_bulk_backfill'
               ORDER BY period_start"""
        )]
        candidates = [dict(row) for row in connection.execute(
            """SELECT c.candidate_id,c.stable_event_id,c.company_name,c.announcement_date,
                      c.round_original,c.round_bucket,c.amount_original,c.investors_original,
                      c.evidence_grade,c.review_status,s.source_title,s.source_url,s.access_status,
                      p.proposal_type,i.name proposed_industry
               FROM v35_historical_candidates c
               JOIN v35_collection_batches b USING(batch_id)
               JOIN v35_candidate_sources s USING(candidate_id)
               JOIN v35_classification_proposals p USING(candidate_id)
               LEFT JOIN v30_industries i ON i.industry_id=p.existing_industry_id AND i.taxonomy_version='V3.2'
               WHERE b.created_by='v35_bulk_backfill'
               ORDER BY c.announcement_date,c.company_name,c.round_original,s.source_url"""
        )]
        raw = [dict(row) for row in connection.execute(
            """SELECT r.published_date,r.source_name,r.source_title,r.source_url,
                      r.screening_status,r.screening_reason
               FROM v35_collection_search_results r JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by='v35_bulk_backfill'
               ORDER BY r.published_date,r.source_url"""
        )]
        daily = {row["search_date"]: dict(row) for row in connection.execute(
            """SELECT s.search_date,SUM(s.result_count) raw_count,SUM(s.valid_result_count) valid_articles,
                      GROUP_CONCAT(DISTINCT s.status) statuses
               FROM v35_collection_searches s JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by IN ('v35_bulk_backfill','codex_v35_trial')
               GROUP BY s.search_date"""
        )}
        legacy_daily = {row["disclosure_date"]: row["n"] for row in connection.execute(
            "SELECT disclosure_date,COUNT(*) n FROM v30_historical_records GROUP BY disclosure_date"
        )}
        industry_rows = [dict(row) for row in connection.execute(
            """SELECT COALESCE(i.name,'待判断/现有体系外') industry,COUNT(*) event_count,
                      SUM(CASE WHEN c.round_bucket='vc' THEN 1 ELSE 0 END) vc,
                      SUM(CASE WHEN c.round_bucket='early' THEN 1 ELSE 0 END) early,
                      SUM(CASE WHEN c.round_bucket='pending' THEN 1 ELSE 0 END) pending
               FROM v35_historical_candidates c JOIN v35_collection_batches b USING(batch_id)
               JOIN v35_classification_proposals p USING(candidate_id)
               LEFT JOIN v30_industries i ON i.industry_id=p.existing_industry_id AND i.taxonomy_version='V3.2'
               WHERE b.created_by='v35_bulk_backfill'
               GROUP BY COALESCE(i.name,'待判断/现有体系外') ORDER BY event_count DESC"""
        )]
        trial = dict(connection.execute(
            """SELECT COUNT(*) events,SUM(round_bucket='vc') vc,SUM(round_bucket='early') early,
                      SUM(round_bucket='pending') pending FROM v35_historical_candidates c
               JOIN v35_collection_batches b USING(batch_id) WHERE b.created_by='codex_v35_trial'"""
        ).fetchone())
        bulk = dict(connection.execute(
            """SELECT COUNT(*) events,COUNT(DISTINCT company_name) companies,SUM(round_bucket='vc') vc,
                      SUM(round_bucket='early') early,SUM(round_bucket='pending') pending
               FROM v35_historical_candidates c JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by='v35_bulk_backfill'"""
        ).fetchone())
        legacy_events = [dict(row) for row in connection.execute(
            """SELECT e.cluster_id unique_event_id,h.disclosure_date,h.round_original
               FROM v35_event_clusters e JOIN v30_historical_records h ON h.record_id=e.canonical_record_id"""
        )]
        v35_events = [dict(row) for row in connection.execute(
            """SELECT stable_event_id unique_event_id,announcement_date,round_original
               FROM v35_historical_candidates"""
        )]

    coverage = []
    for day in all_days(date(2025, 12, 1), date(2026, 11, 25)):
        text = day.isoformat()
        if text in daily:
            row = daily[text]
            state = "searched_with_events" if row["valid_articles"] else "searched_no_valid_result"
            basis = "V3.5逐日检索日志"
            raw_count = row["raw_count"]
            event_count = row["valid_articles"]
        elif day <= date(2026, 11, 24):
            state = "legacy_window_documented"
            basis = "NOVEMBER_2026_FUNDING_DISCOVERY.md记录2026-11-01至11-24检索窗口；无逐日检索日志"
            raw_count = ""
            event_count = legacy_daily.get(text, 0)
        else:
            state = "legacy_records_only"
            basis = "数据库含当日历史记录，但旧检索报告截止11月24日；缺少11月25日检索审计"
            raw_count = ""
            event_count = legacy_daily.get(text, 0)
        coverage.append({"date": text, "coverage_state": state, "raw_article_count": raw_count,
                         "valid_article_or_legacy_record_count": event_count, "coverage_basis": basis})

    combined_events = v35_events + legacy_events
    windows = {days: rolling_window(combined_events, days, cutoff="2026-11-25") for days in (30, 90, 360)}
    window_rows = [{"window_days": days, "start_date": value["start_date"], "end_date": value["end_date"],
                    "event_count": len(value["events"]), "coverage_complete": value["coverage_complete"]}
                   for days, value in windows.items()]
    screening = Counter(row["screening_status"] for row in raw)
    sources = {(row["candidate_id"], row["source_url"]) for row in candidates}
    unique_events = {row["stable_event_id"] for row in candidates}
    coverage_counts = Counter(row["coverage_state"] for row in coverage)

    write_csv("V35_330_DAY_MONTHLY_SUMMARY.csv", batches)
    write_csv("V35_330_DAY_CANDIDATES.csv", candidates)
    write_csv("V35_330_DAY_RAW_RESULTS.csv", raw)
    write_csv("V35_360_DAY_COVERAGE.csv", coverage)
    write_csv("V35_330_DAY_INDUSTRY_DISTRIBUTION.csv", industry_rows)
    write_csv("V35_ROLLING_WINDOW_READINESS.csv", window_rows)

    monthly_lines = ["| 月份 | 原始文章 | 有效事件 | VC | 种子/天使 | 待核验 | 重复报道 |",
                     "|---|---:|---:|---:|---:|---:|---:|"]
    for row in batches:
        monthly_lines.append(
            f"| {row['period_start'][:7]} | {row['raw_source_count']} | {row['new_candidate_count']} | "
            f"{row['vc_event_count']} | {row['early_event_count']} | {row['pending_round_count']} | {row['duplicate_source_count']} |"
        )
    industry_lines = ["| 产业领域 | 事件 | VC | 种子/天使 | 待核验 |", "|---|---:|---:|---:|---:|"]
    for row in industry_rows:
        industry_lines.append(f"| {row['industry']} | {row['event_count']} | {row['vc']} | {row['early']} | {row['pending']} |")
    window_lines = ["| 窗口 | 起止日期 | 去重事件 | 覆盖完整 |", "|---|---|---:|---|"]
    for row in window_rows:
        window_lines.append(f"| {row['window_days']}天 | {row['start_date']} 至 {row['end_date']} | {row['event_count']} | {row['coverage_complete']} |")

    report = f"""# V3.5 330天历史融资回填验收报告

## 范围与方法

- 新采集区间：2025-12-01至2026-10-26，共330个自然日。
- 数据源：投资界融资频道公开逐日归档及可访问正文；正文缓存仅用于本地证据复核。
- 搜索不使用V3.2十个一级领域作为关键词过滤；产业匹配在事件形成后执行。
- 所有新增事件保留在V3.5候选层，未写入正式融资事件表，未修改V3.2冻结分类。
- 36氪公开搜索和IT桔子公开入口未形成可稳定自动化的全时段正文来源，因此本轮不能宣称多来源全市场穷尽。

## 330天采集结果

- 原始归档文章：{len(raw)}
- 候选融资事件：{bulk['events']}
- 去重企业：{bulk['companies']}
- VC事件：{bulk['vc']}
- 种子/天使事件：{bulk['early']}
- 轮次待核验：{bulk['pending']}
- 原始筛选：候选文章{screening['candidate']}，轮次待核验文章{screening['needs_verification']}，排除文章{screening['excluded']}。
- 稳定事件ID：{len(unique_events)}个；候选来源映射：{len(sources)}条。
- 22个试采事件保持独立存在：VC {trial['vc']}、种子/天使 {trial['early']}、待核验 {trial['pending']}。

## 月度统计

{chr(10).join(monthly_lines)}

## 产业分类建议

分类为自动候选建议，全部保持pending，不升级V3.2分类体系。无法可靠匹配现有一级领域的事件保留为“待判断/现有体系外”，作为后续新一级领域或跨领域候选池。

{chr(10).join(industry_lines)}

## 360天日期覆盖

- V3.5逐日检索日志：{coverage_counts['searched_with_events'] + coverage_counts['searched_no_valid_result']}天。
- 已检索且有有效文章：{coverage_counts['searched_with_events']}天。
- 已检索但无有效结果：{coverage_counts['searched_no_valid_result']}天。
- 旧检索报告证明窗口覆盖但缺逐日日志：{coverage_counts['legacy_window_documented']}天。
- 仅有旧数据库记录、缺少检索审计：{coverage_counts['legacy_records_only']}天（2026-11-25）。

因此，2025-12-01至2026-11-24共359天有检索窗口证据；2026-11-25有2条旧记录，但缺少该日完整检索日志，不能将其表述为“完成全量检索”。

## 30/90/360天统计准备

现有`rolling_window`逻辑已用V3.5候选事件与95个旧稳定事件簇的统一事件形状完成只读验证。候选数据没有混入正式网站统计或正式Release。

{chr(10).join(window_lines)}

## 数据质量与限制

- 同企业、同轮次、同金额且30天内的重复报道自动合并，保留最早披露事件和全部来源。
- 候选层全部为自动筛选结果，未进行人工审核；轮次、企业实体和产业匹配仍可能存在需人工修正项。
- 单一媒体源不能证明全市场绝对完整；缺少稳定的36氪、IT桔子及官方公众号历史索引是主要来源缺口。
- 2026-11-25缺少旧流程逐日检索日志，是360天审计中唯一未闭合的日期。
"""
    (DOCS / "V35_330_DAY_BACKFILL_ACCEPTANCE.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
