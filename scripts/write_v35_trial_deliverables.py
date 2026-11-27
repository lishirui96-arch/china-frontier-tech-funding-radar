from __future__ import annotations

import csv
from pathlib import Path

from funding_radar.db import connect


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row.get(column) for column in columns} for row in rows)


def main() -> None:
    connection = connect(read_only=True)
    try:
        candidates = [dict(row) for row in connection.execute(
            """SELECT c.stable_event_id,c.company_name,c.announcement_date,c.round_original,c.round_bucket,
                      c.amount_original,c.amount_currency,c.investors_original,c.primary_business,c.core_technology,
                      c.evidence_grade,c.review_status,s.source_name,s.source_title,s.source_url,
                      p.proposal_type,p.proposed_topic_name,p.existing_industry_id,p.existing_field_id,p.existing_topic_id,
                      p.review_status classification_review_status
                 FROM v35_historical_candidates c
                 JOIN v35_candidate_sources s USING(candidate_id)
                 JOIN v35_classification_proposals p USING(candidate_id)
                ORDER BY c.announcement_date,c.company_name,c.round_original"""
        )]
        searches = [dict(row) for row in connection.execute(
            "SELECT search_date,source_name,query_text,result_count,valid_result_count,status,notes,searched_at FROM v35_collection_searches ORDER BY search_date,source_name"
        )]
        mapping = [dict(row) for row in connection.execute(
            """SELECT m.cluster_id,m.record_id,m.legacy_unique_event_id,m.member_role,m.mapping_reason,
                      m.source_merge_id,m.mapped_by,m.mapped_at
                 FROM v35_event_cluster_members m ORDER BY m.cluster_id,m.member_role,m.record_id"""
        )]
        raw = [dict(row) for row in connection.execute(
            "SELECT published_date,source_name,source_title,source_url,screening_status,screening_reason FROM v35_collection_search_results ORDER BY published_date,source_url"
        )]
    finally:
        connection.close()

    write_csv(DOCS / "V35_TRIAL_CANDIDATES.csv", candidates, list(candidates[0]))
    write_csv(DOCS / "V35_COLLECTION_SEARCH_LOG.csv", searches, list(searches[0]))
    write_csv(DOCS / "V35_EVENT_CLUSTER_MAPPING.csv", mapping, list(mapping[0]))
    write_csv(DOCS / "V35_TRIAL_RAW_RESULTS.csv", raw, list(raw[0]))

    links = "\n".join(
        f"- {row['published_date']} | {row['source_title']} | [{row['source_name']}]({row['source_url']}) | {row['screening_status']}"
        for row in raw
    )
    report = f"""# V3.5历史融资基础层与首批试采验收报告

## 执行范围

- 统计截止日：2026-11-25
- 本批试采：2026-10-27至2026-11-01
- 搜索范围：中国科技产业全领域，不以V3.2十个一级领域作为采集过滤条件
- 目标轮次：种子/天使及Pre-A至B++；其他轮次排除或保留待核验
- 发布隔离：新增数据仅进入V3.5候选与建议层，未进入正式事件、V3.2冻结分类或公开Release

## 基础层修复

- 新建95个稳定事件簇，映射97条不可变历史来源记录。
- 95条主记录沿用原有稳定事件ID；谱星航天和蓝固新能源的2条重复来源映射到各自主事件簇。
- 旧`unique_event_id`完整保存在`legacy_unique_event_id`，未修改或删除旧记录。
- 每个簇成员保留映射理由、V3.4合并决策ID、操作人和时间。
- 批次、检索、原始命中、候选事件、来源证据和分类建议均建立独立审计表。

## 试采统计

| 指标 | 结果 |
|---|---:|
| 实际检索原始资讯 | 25 |
| 形成候选的文章 | 18 |
| 去重后候选事件 | 22 |
| VC事件 | 12 |
| 种子/天使事件 | 7 |
| 轮次待确认事件 | 3 |
| 待人工审核事件 | 22 |
| 匹配现有10个一级领域 | 22 |
| 直接匹配现有二/三级分类 | 15 |
| 新二/三级技术分类建议 | 7 |
| 新一级产业领域候选 | 0 |
| 重复来源 | 0 |
| 明确排除资讯 | 7 |

3篇文章明确披露了两个不同轮次，分别建立事件ID：扰动之心的天使轮/天使+轮、宜诺生物的天使轮/Pre-A轮、百世达的天使轮/天使+轮。合计金额没有拆分，不进行推算。

澜昆微电子报道明确为两轮融资，但未披露轮次及单轮金额，因此保留两个轮次待核验事件；伏尔坎未披露轮次，保留一个待核验事件。

## 分类扩展结果

全部22个事件均可合理归入现有10个一级领域，没有足够证据提出新一级领域。以下7个产品级方向进入三级主题建议队列，均为`pending`：

1. 机器嗅觉芯片与气味感知系统
2. 妇科微创诊疗与有源医疗器械
3. 小分子创新药与差异化靶点
4. 高纯难熔金属与智能提纯装备
5. 物理AI数据与世界模型基础设施
6. 特种运输装备与精密载运系统
7. 铌酸锂光电材料与器件基质

这些建议不修改V3.2冻结目录；单条事件只作为候选依据，不能自动升级为正式主题。

## 日期覆盖

| 日期 | 原始命中 | 形成候选的文章 | 候选事件 |
|---|---:|---:|---:|
| 2026-10-27 | 5 | 3 | 4 |
| 2026-10-28 | 6 | 5 | 6 |
| 2026-10-29 | 7 | 6 | 7 |
| 2026-10-30 | 7 | 4 | 5 |
| 2026-10-31 | 0 | 0 | 0 |
| 2026-11-01 | 0 | 0 | 0 |

10月31日和11月1日已检索但没有找到符合本批条件且正文可核验的融资事件，未生成占位或虚构记录。

## 来源与检索限制

- 投资界融资频道：可访问，逐日归档和正文完成核验。
- 36氪：公开搜索页未返回目标日期可核验正文，记为无有效结果。
- IT桔子：公开入口返回HTTP 412，未绕过访问限制，记为失败。
- 公开网页检索：排除上市公司融资融券、IPO、产业基金、战略投资等噪声。
- 企业及投资机构官方公告未发现可稳定索引的独立原文链接，本批证据等级保持B，不提升为A级。

因此，本批完成了可追溯试采流程验证，但不能将单一来源结果宣称为全市场绝对完整覆盖。扩大历史批量前，需要增加可稳定访问的36氪、IT桔子或官方公告索引渠道。

## 原始资讯链接

{links}

## 交付文件

- `docs/V35_TRIAL_CANDIDATES.csv`
- `docs/V35_TRIAL_RAW_RESULTS.csv`
- `docs/V35_COLLECTION_SEARCH_LOG.csv`
- `docs/V35_EVENT_CLUSTER_MAPPING.csv`
- `docs/V35_TRIAL_BACKFILL_ACCEPTANCE.md`

## 保护确认

- 未修改V3.2产业、领域或主题目录。
- 未修改原有95个有效候选事件。
- 未删除97条原始来源记录。
- 未新增正式融资事件。
- 未修改网站UI或现有Release。
- 未执行2026-10-26及更早月份的批量采集。
"""
    (DOCS / "V35_TRIAL_BACKFILL_ACCEPTANCE.md").write_text(report, encoding="utf-8")
    print({"candidate_rows": len(candidates), "raw_results": len(raw), "mapping_rows": len(mapping), "search_logs": len(searches)})


if __name__ == "__main__":
    main()
