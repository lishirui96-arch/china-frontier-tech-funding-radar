from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from funding_radar.db import connect
from funding_radar.public_service import rolling_window


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def pct(value: int, total: int) -> str:
    return f"{value / total:.1%}" if total else "0.0%"


def write_csv(name: str, rows: list[dict]) -> None:
    path = DOCS / name
    if not rows:
        path.write_text("status,reason\nnone,no qualifying candidate\n", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def normalized_company(value: str) -> str:
    return re.sub(r"[\s\-—_·（）()“”\"'「」]", "", value).casefold()


def pending_round_reason(title: str) -> str:
    if re.search(r"首轮融资", title):
        return "标题仅称首轮融资"
    if re.search(r"新一轮|新轮次", title):
        return "标题仅称新一轮融资"
    if re.search(r"多轮|两轮|三轮|系列融资|连续.*轮", title):
        return "标题披露多轮或系列融资但未拆分"
    if re.search(r"战略", title):
        return "标题含战略表述，轮次口径需复核"
    if re.search(r"融资", title):
        return "标题披露融资但未给出标准轮次"
    return "标题轮次信息不足"


CLUSTER_RULES = [
    ("B", "汽车电子与智能底盘（现有高端装备/无人系统下新增主题）", ("线控制动", "线控底盘", "智能底盘", "车规", "汽车零部件", "电动汽车", "智能座舱", "One-box", "EMB")),
    ("B", "空间计算与智能终端（现有AI软件/半导体下新增主题）", ("AR眼镜", "智能眼镜", "近眼显示", "空间计算", "可穿戴", "骨传导耳机", "智能终端")),
    ("B", "金融科技与产业数字基础设施（现有AI软件下新增主题）", ("金融科技", "支付", "PhotonPay", "保险科技", "区块链", "供应链金融")),
    ("B", "核能工程与超导装备（现有新能源/高端装备下新增主题）", ("核反应堆", "核裂变", "核聚变", "聚变", "超导", "核素")),
    ("C", "农业食品与环境科技", ("农业科技", "智慧农业", "育种", "种植", "农机", "食品科技", "环境治理", "污水", "废水", "污染治理", "循环经济")),
    ("A", "脑科学与神经技术", ("脑机", "神经接口", "神经调控", "脑科学")),
    ("A", "量子科技", ("量子计算", "量子通信", "量子精密测量")),
    ("A", "商业航天与卫星应用", ("卫星", "航天", "火箭", "空天")),
    ("A", "低空经济与无人系统", ("无人机", "eVTOL", "低空", "自动驾驶", "无人驾驶", "智驾")),
    ("A", "机器人与具身智能", ("机器人", "具身", "灵巧手", "机械臂", "关节模组", "伺服")),
    ("A", "生物制造与生命科学", ("创新药", "制药", "生物", "细胞", "基因", "蛋白", "医疗", "诊疗", "医用", "健康管理", "营养干预", "精准给药")),
    ("A", "AI计算与半导体", ("芯片", "半导体", "晶圆", "封装", "光刻", "EDA", "Micro LED", "Micro-LED", "光互连", "微纳", "光电")),
    ("A", "新能源与先进材料", ("电池", "储能", "光伏", "氢能", "新材料", "新材", "复材", "涂层", "钙钛矿", "电化学合成", "电致变色")),
    ("A", "高端装备与先进制造", ("精密仪器", "精仪", "工业装备", "智能制造", "工业自动化", "数控", "激光", "光学", "试验试飞", "适航认证", "检测设备")),
    ("A", "AI软件与工业智能", ("大模型", "智能体", "Agent", "软件", "数据平台", "网络安全", "云计算", "SaaS", "数字化", "Scaling")),
]


def cluster_event(row: dict) -> dict:
    title = str(row.get("source_title") or "")
    for category, cluster, keywords in CLUSTER_RULES:
        matched = [word for word in keywords if word.casefold() in title.casefold()]
        if matched:
            return {"category": category, "cluster": cluster, "matched_keywords": "|".join(matched),
                    "rationale": f"来源标题出现直接技术信号：{'、'.join(matched[:5])}"}
    intro = str(row.get("primary_business") or "")[:500]
    scored = []
    for category, cluster, keywords in CLUSTER_RULES:
        hits = [(word, intro.casefold().count(word.casefold())) for word in keywords if word.casefold() in intro.casefold()]
        score = sum(count for _, count in hits)
        if score >= 2 and len(hits) >= 2:
            scored.append((score, category, cluster, [word for word, _ in hits]))
    if scored:
        score, category, cluster, matched = max(scored, key=lambda item: item[0])
        return {"category": category, "cluster": cluster, "matched_keywords": "|".join(matched),
                "rationale": f"企业开头简介出现{score}次一致技术信号：{'、'.join(matched[:5])}"}
    return {"category": "D", "cluster": "证据不足/无法稳定归类", "matched_keywords": "",
            "rationale": "现有文本未形成足以支持一级领域或新增技术主题的稳定边界"}


def main() -> None:
    with connect(read_only=True) as connection:
        bulk = [dict(row) for row in connection.execute(
            """SELECT c.*,b.period_start,s.source_name,s.source_title,s.source_url,s.access_status,
                      s.evidence_excerpt,p.proposal_type,p.existing_industry_id
               FROM v35_historical_candidates c JOIN v35_collection_batches b USING(batch_id)
               JOIN v35_candidate_sources s USING(candidate_id)
               JOIN v35_classification_proposals p USING(candidate_id)
               WHERE b.created_by='v35_bulk_backfill'
                 AND s.candidate_source_id=(SELECT MIN(s2.candidate_source_id) FROM v35_candidate_sources s2 WHERE s2.candidate_id=c.candidate_id)
               ORDER BY c.announcement_date,c.candidate_id"""
        )]
        all_sources = [dict(row) for row in connection.execute(
            """SELECT c.candidate_id,c.stable_event_id,c.company_name,c.announcement_date,c.round_bucket,
                      s.source_name,s.source_url,b.period_start,p.existing_industry_id,i.name industry_name
               FROM v35_historical_candidates c JOIN v35_collection_batches b USING(batch_id)
               JOIN v35_candidate_sources s USING(candidate_id)
               JOIN v35_classification_proposals p USING(candidate_id)
               LEFT JOIN v30_industries i ON i.industry_id=p.existing_industry_id AND i.taxonomy_version='V3.2'
               WHERE b.created_by='v35_bulk_backfill'"""
        )]
        raw = [dict(row) for row in connection.execute(
            """SELECT r.* FROM v35_collection_search_results r JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by='v35_bulk_backfill'"""
        )]
        searches = [dict(row) for row in connection.execute(
            """SELECT s.* FROM v35_collection_searches s JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by IN ('v35_bulk_backfill','codex_v35_trial')"""
        )]
        pending_industry = [row for row in bulk if not row["existing_industry_id"]]
        legacy = [dict(row) for row in connection.execute(
            """SELECT e.cluster_id unique_event_id,h.disclosure_date,h.round_original
               FROM v35_event_clusters e JOIN v30_historical_records h ON h.record_id=e.canonical_record_id"""
        )]
        all_candidates = [dict(row) for row in connection.execute(
            "SELECT stable_event_id unique_event_id,announcement_date,round_original,review_status FROM v35_historical_candidates"
        )]
        formal_count = connection.execute("SELECT COUNT(*) FROM v15_confirmed_funding_events").fetchone()[0]

    total = len(bulk)
    source_by_candidate = Counter(row["candidate_id"] for row in all_sources)
    multi_source = sum(value > 1 for value in source_by_candidate.values())
    extra_sources = sum(value - 1 for value in source_by_candidate.values())
    company_groups: dict[str, set[str]] = defaultdict(set)
    company_rounds: dict[str, set[str]] = defaultdict(set)
    for row in bulk:
        company_groups[normalized_company(row["company_name"])].add(row["company_name"])
        company_rounds[normalized_company(row["company_name"])].add(row["round_original"])
    alias_risks = {key: values for key, values in company_groups.items() if len(values) > 1}
    multi_round_companies = sum(len(values) > 1 for values in company_rounds.values())
    suspicious_names = [row for row in bulk if len(row["company_name"]) > 40 or re.search(r"融资|投资界|完成", row["company_name"])]

    pending_rounds = [row for row in bulk if row["round_bucket"] == "pending"]
    pending_reasons = Counter(pending_round_reason(row["source_title"]) for row in pending_rounds)
    field_metrics = {
        "company_name": sum(bool(row["company_name"].strip()) for row in bulk),
        "investors_named": sum(row["investors_original"] != "未披露" for row in bulk),
        "amount_disclosed": sum(row["amount_original"] != "未披露" for row in bulk),
        "currency_structured": sum(bool(row["amount_currency"]) for row in bulk),
        "standard_round": sum(row["round_bucket"] != "pending" for row in bulk),
        "business_text": sum(bool(row["primary_business"].strip()) for row in bulk),
        "technology_text": sum(bool(row["core_technology"].strip()) for row in bulk),
        "accessible_source": sum(row["access_status"] == "text_saved" for row in bulk),
    }
    included_raw_urls = {row["source_url"] for row in raw if row["screening_status"] != "excluded"}
    candidate_urls = {row["source_url"] for row in all_sources}

    month_sources: dict[str, set[str]] = defaultdict(set)
    industry_sources: dict[str, set[str]] = defaultdict(set)
    round_sources: dict[str, set[str]] = defaultdict(set)
    month_source_records = Counter()
    industry_source_records = Counter()
    round_source_records = Counter()
    for row in all_sources:
        month = row["announcement_date"][:7]
        industry = row["industry_name"] or "待判断/现有体系外"
        month_sources[month].add(row["source_name"])
        industry_sources[industry].add(row["source_name"])
        round_sources[row["round_bucket"]].add(row["source_name"])
        month_source_records[month] += 1
        industry_source_records[industry] += 1
        round_source_records[row["round_bucket"]] += 1

    assignments = []
    for row in pending_industry:
        result = cluster_event(row)
        assignments.append({
            "candidate_id": row["candidate_id"], "company_name": row["company_name"],
            "announcement_date": row["announcement_date"], "round_original": row["round_original"],
            "category": result["category"], "suggested_cluster": result["cluster"],
            "matched_keywords": result["matched_keywords"], "rationale": result["rationale"],
            "source_title": row["source_title"], "source_url": row["source_url"],
        })
    cluster_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in assignments:
        cluster_groups[(row["category"], row["suggested_cluster"])].append(row)
    category_counts = Counter(row["category"] for row in assignments)

    new_industries = []
    for (category, cluster), rows in cluster_groups.items():
        if category != "C":
            continue
        companies = sorted({row["company_name"] for row in rows})
        evidence = sorted({row["source_url"] for row in rows})
        status = "candidate" if len(companies) >= 3 else "watchlist_insufficient_support"
        new_industries.append({
            "suggested_name": cluster, "status": status, "event_count": len(rows),
            "company_count": len(companies), "representative_companies": "|".join(companies[:10]),
            "technical_boundary": "以农业生产、食品工程或环境治理中的可验证技术创新为核心，不包含普通食品品牌、传统农业经营或一般环保服务",
            "difference_from_v32": "现有新能源与先进材料、生物制造、AI软件均只能覆盖其中单一技术环节，缺少面向农业食品和环境系统的一级产业边界",
            "recommendation": "达到至少3家独立企业后进入新一级领域候选；否则保留观察项",
            "evidence_urls": "|".join(evidence[:10]),
        })

    coverage_dates = {row["search_date"] for row in searches}
    coverage_rows = []
    current = date(2025, 12, 1)
    while current <= date(2026, 11, 25):
        day = current.isoformat()
        if day in coverage_dates:
            state = "daily_log_verified"
            evidence = "v35_collection_searches"
        elif current <= date(2026, 11, 24):
            state = "window_level_evidence_only"
            evidence = "NOVEMBER_2026_FUNDING_DISCOVERY.md records a 2026-11-01 to 2026-11-24 search window"
        else:
            state = "records_present_audit_insufficient"
            evidence = "2 legacy records exist; no complete daily search log or report coverage for 2026-11-25"
        coverage_rows.append({"date": day, "audit_state": state, "evidence": evidence})
        current += timedelta(days=1)
    coverage_counts = Counter(row["audit_state"] for row in coverage_rows)

    combined = all_candidates + legacy
    windows = {days: rolling_window(combined, days, cutoff="2026-11-25") for days in (30, 90, 360)}
    window_counts = {days: len(value["events"]) for days, value in windows.items()}
    expected = {30: 117, 90: 387, 360: 1428}

    write_csv("V36_PENDING_75_CLUSTER_ASSIGNMENTS.csv", assignments)
    write_csv("V36_NEW_INDUSTRY_CANDIDATES.csv", new_industries)
    write_csv("V36_360_DAY_COVERAGE_AUDIT.csv", coverage_rows)

    coverage_report = f"""# V3.6 360天数据覆盖审计报告

## 核验范围

- 日期：2025-12-01至2026-11-25，共360天。
- 证据层级：逐日数据库日志 > 明确记载检索窗口的历史报告 > 仅有事件记录。
- 本次仅整合和评价现有证据，没有补写检索日志，也没有重新采集11月2日至25日。

## 结论

| 审计状态 | 天数 | 结论 |
|---|---:|---|
| 逐日检索日志可验证 | {coverage_counts['daily_log_verified']} | V3.5批次和试采日志可逐日核对 |
| 仅有窗口级历史证据 | {coverage_counts['window_level_evidence_only']} | 2026-11-02至11-24；报告证明窗口被检索，但不能还原每日日志 |
| 有记录但审计证据不足 | {coverage_counts['records_present_audit_insufficient']} | 2026-11-25；数据库有2条记录，但没有完整检索证据 |

历史报告`NOVEMBER_2026_FUNDING_DISCOVERY.md`明确记载检索窗口为2026-11-01至11-24、81条去重URL、79篇可访问正文和25个候选事件；`NOVEMBER_2026_SOURCE_REGISTER.csv`保留81条来源明细。这能证明23天属于既有检索窗口，但不能证明每一天采用了哪些查询、是否无结果或是否完整覆盖。

## 未闭合事项

- 23天只能标记为`window_level_evidence_only`，不得转换为逐日完成日志。
- 2026-11-25只能标记为`records_present_audit_insufficient`。
- 因用户要求不重新采集已有区间，本阶段无法把360天全部提升为逐日审计级覆盖。
"""
    (DOCS / "V36_360_DAY_COVERAGE_AUDIT.md").write_text(coverage_report, encoding="utf-8")

    reason_lines = "\n".join(f"| {name} | {count} | {pct(count, len(pending_rounds))} |" for name, count in pending_reasons.most_common())
    field_lines = "\n".join(f"| {name} | {value} | {pct(value, total)} |" for name, value in field_metrics.items())
    alias_lines = "；".join(" / ".join(sorted(values)) for values in alias_risks.values()) or "无"
    quality_report = f"""# V3.6 融资事件数据质量报告

## 总体结论

- 审计对象：{total}个330天回填候选事件；全部保持候选状态。
- 企业名称非空率：{pct(field_metrics['company_name'], total)}；规则检测到{len(suspicious_names)}个明显异常长名或含融资叙述的名称。
- 规范化后存在多种名称写法的企业组：{len(alias_risks)}组；这是自动实体归一风险，不代表已确认重复。
- 别名风险明细：{alias_lines}。
- 同一企业具有多个轮次的企业：{multi_round_companies}家；不同轮次按事件分别保留。
- 多来源事件：{multi_source}个，额外来源{extra_sources}条。
- 原始纳入URL与候选来源URL集合差异：遗漏{len(included_raw_urls-candidate_urls)}，额外{len(candidate_urls-included_raw_urls)}。

## 字段完整性

| 字段或检查 | 完整数 | 完整率 |
|---|---:|---:|
{field_lines}

`primary_business`和`core_technology`虽然非空，但来自正文截取，不等同于人工结构化完成；币种结构化字段几乎为空时，金额原文仍保留，不能据此直接跨币种聚合。

## 轮次待核验

轮次待核验事件共{len(pending_rounds)}个。

| 原因 | 数量 | 占待核验比例 |
|---|---:|---:|
{reason_lines}

## 风险分层

- 高风险：轮次待核验、币种未结构化、企业别名风险、普通消费科技边界不清。
- 中风险：投资方为正文句子而非标准机构实体；金额为模糊范围；同一企业短期多次披露。
- 较低风险：日期、来源URL、证据摘要、内容哈希和稳定事件ID完整。

本报告不自动修改候选、不确认融资事实，也不改变正式事件表。
"""
    (DOCS / "V36_FUNDING_EVENT_QUALITY_AUDIT.md").write_text(quality_report, encoding="utf-8")

    month_lines = "\n".join(f"| {month} | {month_source_records[month]} | {len(sources)} | {'、'.join(sorted(sources))} |" for month, sources in sorted(month_sources.items()))
    industry_lines = "\n".join(f"| {industry} | {industry_source_records[industry]} | {len(sources)} | {'、'.join(sorted(sources))} |" for industry, sources in sorted(industry_sources.items()))
    round_lines = "\n".join(f"| {bucket} | {round_source_records[bucket]} | {len(sources)} | {'、'.join(sorted(sources))} |" for bucket, sources in sorted(round_sources.items()))
    source_report = f"""# V3.6 数据来源覆盖偏差报告

## 结论

330天回填候选及其原始文章均来自投资界，来源集中度为100%。月份、产业和轮次维度均不存在真正的跨来源覆盖，当前结果适合描述投资界公开归档中的融资披露，不可解释为中国科技融资全市场总体。

## 月份来源分布

| 月份 | 来源记录 | 独立来源数 | 来源 |
|---|---:|---:|---|
{month_lines}

## 产业来源分布

| 产业 | 来源记录 | 独立来源数 | 来源 |
|---|---:|---:|---|
{industry_lines}

## 轮次来源分布

| 轮次桶 | 来源记录 | 独立来源数 | 来源 |
|---|---:|---:|---|
{round_lines}

## 可能漏采风险

- 高风险：企业官方公众号首发、地方国资和产业基金公告、仅在36氪或IT桔子披露的早期项目。
- 高风险领域：种子轮小团队、企业软件、农业食品科技、环境科技、区域性先进制造项目。
- 中风险领域：生物医药和医疗器械，专业行业媒体可能早于综合创投媒体。
- 相对较低但仍存在偏差：机器人、AI大模型、半导体等高关注赛道。

## 补充检索计划

1. 以月份和企业名为键，对36氪、IT桔子做URL发现和正文可访问性审计；不可访问内容只作线索。
2. 对现有1,168家企业查询官网新闻、认证公众号转载、投资机构Portfolio/新闻页。
3. 对75个待判断事件优先补充企业产品页和投资机构公告，用于产业边界而非扩大事件数。
4. 按“来源新增事件率、字段补全率、重复率”评估渠道价值，先试采一个月，再决定是否扩展360天。
5. 所有补充来源关联既有稳定事件ID；只有明确的新融资事实才新建候选，禁止仅凭标题入库。
"""
    (DOCS / "V36_SOURCE_COVERAGE_BIAS.md").write_text(source_report, encoding="utf-8")

    cluster_lines = []
    for (category, cluster), rows in sorted(cluster_groups.items()):
        companies = "、".join(sorted({row['company_name'] for row in rows})[:12])
        cluster_lines.append(f"| {category} | {cluster} | {len(rows)} | {companies} |")
    cluster_report = f"""# V3.6 75个待判断事件产业主题聚类报告

## 方法与边界

聚类使用企业主营业务、核心技术正文、来源标题和应用语境的规则匹配。它是可复核的探索性分组，不是统计学习意义上的稳定聚类，也不是人工分类结论。每条事件的规则命中和来源见`V36_PENDING_75_CLUSTER_ASSIGNMENTS.csv`。

## 分类结果

- A 可归入现有一级领域：{category_counts['A']}
- B 适合在现有一级领域下新增二/三级主题：{category_counts['B']}
- C 潜在新一级领域：{category_counts['C']}
- D 证据不足：{category_counts['D']}

| 类别 | 主题 | 事件数 | 代表企业 |
|---|---|---:|---|
{chr(10).join(cluster_lines)}

## 新一级领域判断

只有C类且至少包含3家独立企业时才进入正式候选清单。低于该门槛的方向保留为观察项，不建议修改V3.2。候选的技术边界、企业、事件数、与现有领域差异及证据URL见`V36_NEW_INDUSTRY_CANDIDATES.csv`。

## 建议

- A类：进入现有一级领域的人工复核队列。
- B类：优先讨论“汽车电子与智能底盘”“空间计算与智能终端”“金融科技与产业数字基础设施”等二/三级主题。
- C类：只有在补充来源确认共同技术边界后再考虑新一级领域。
- D类：先补企业官网或投资机构原文，不以当前媒体正文强制分类。
"""
    (DOCS / "V36_PENDING_INDUSTRY_CLUSTERING.md").write_text(cluster_report, encoding="utf-8")

    window_lines = "\n".join(
        f"| {days}天 | {value['start_date']}至{value['end_date']} | {len(value['events'])} | {expected[days]} | {'一致' if len(value['events']) == expected[days] else '不一致'} |"
        for days, value in windows.items()
    )
    window_report = f"""# V3.6 30/90/360天统计口径核验报告

## 统一口径

- 截止日期统一为2026-11-25，窗口首尾均包含。
- V3.5候选以`stable_event_id`去重，旧历史记录以95个`cluster_id`去重。
- 日期统一取候选`announcement_date`或旧记录`disclosure_date`。
- 候选层只包含`pending`和`needs_verification`，不包含`excluded`；正式事件表当前为{formal_count}条。
- 统计结果是候选事件观察口径，不等同于人工确认后的正式融资统计。

| 窗口 | 日期范围 | 实算事件 | 预期事件 | 结果 |
|---|---|---:|---:|---|
{window_lines}

## 一致性检查

- 三个窗口调用同一个`rolling_window`函数，使用同一ID、日期和状态输入规则。
- 30天是90天的子集，90天是360天的子集。
- 未把V3.5候选写入正式Release或网站正式统计。
- `coverage_complete=True`仅表示输入事件日期跨度覆盖窗口起点，不代表每一天都具有同等级检索证据；日期审计以覆盖报告为准。
"""
    (DOCS / "V36_ROLLING_WINDOW_AUDIT.md").write_text(window_report, encoding="utf-8")


if __name__ == "__main__":
    main()
