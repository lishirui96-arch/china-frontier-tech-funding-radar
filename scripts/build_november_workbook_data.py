from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from funding_radar.db import connect
from funding_radar.sample_library import SampleLibraryService


def matrix(rows: list[dict], columns: list[tuple[str,str]]) -> list[list]:
    return [[label for _,label in columns], *[[row.get(key) for key,_ in columns] for row in rows]]


def main() -> None:
    service = SampleLibraryService()
    funding = service.funding_events()
    v11_candidates = service.v11_candidates("verified_new")
    funding.extend([{
        "event_id": row["candidate_id"], "announcement_date": row["disclosure_date"], "transaction_date": None,
        "company_name": row["company_name_original"], "primary_category": "待人工复核", "secondary_track": "待人工复核",
        "financing_type": "candidate", "round_original": row["round_original"], "normalized_round": row["round_normalized"],
        "amount_original": row["amount_original"], "normalized_amount_cny": None, "investors": "待人工复核",
        "use_of_funds_original": None, "source_title": row["title"], "source_url": row["original_url"],
        "evidence_grade": row["evidence_grade"], "review_status": "V1.1新增候选，待人工审核",
    } for row in v11_candidates])
    acquisitions = service.acquisitions()
    profiles = service.technology_profiles()
    keywords = service.keywords()
    themes = service.themes()
    with connect(read_only=True) as c:
        sources = [dict(r) for r in c.execute("""SELECT d.document_id,d.title,d.original_url,d.published_at,d.fetched_at,s.name AS source_name,
            s.evidence_default_grade,d.fetch_status,d.financing_category,d.review_status
          FROM raw_documents d JOIN sources s USING(source_id) WHERE substr(COALESCE(d.published_at,''),1,7)='2026-11' ORDER BY d.published_at,d.title""")]
        round_stats = [dict(r) for r in c.execute("""SELECT normalized_round AS label,COUNT(*) AS event_count,
            COUNT(normalized_amount_cny) AS disclosed_count,SUM(normalized_amount_cny) AS disclosed_amount_cny
          FROM sample_event_profiles WHERE sample_month='2026-11' AND inclusion_status='included' GROUP BY normalized_round ORDER BY normalized_round""")]
        category_stats = [dict(r) for r in c.execute("""SELECT ic.name AS label,COUNT(DISTINCT p.event_id) AS event_count,
            COUNT(DISTINCT e.company_id) AS company_count,COUNT(DISTINCT ei.investor_id) AS investor_count,
            COUNT(p.normalized_amount_cny) AS disclosed_count,SUM(p.normalized_amount_cny) AS disclosed_amount_cny
          FROM sample_event_profiles p JOIN funding_events e USING(event_id) JOIN industry_categories ic USING(category_id)
          LEFT JOIN event_investors ei USING(event_id) WHERE p.sample_month='2026-11' AND p.inclusion_status='included' GROUP BY ic.category_id ORDER BY ic.sort_order""")]
        grade_stats = [dict(r) for r in c.execute("""SELECT evidence_grade AS label,COUNT(*) AS event_count FROM funding_events e JOIN sample_event_profiles p USING(event_id)
          WHERE p.sample_month='2026-11' AND p.inclusion_status='included' GROUP BY evidence_grade ORDER BY evidence_grade""")]
    stats = [["统计维度","类别","事件数","企业数","投资机构数","金额已披露事件数","已披露人民币金额合计","金额披露率"]]
    for row in round_stats:
        stats.append(["融资轮次",row["label"],row["event_count"],None,None,row["disclosed_count"],row["disclosed_amount_cny"],row["disclosed_count"]/row["event_count"] if row["event_count"] else None])
    for row in category_stats:
        stats.append(["一级产业",row["label"],row["event_count"],row["company_count"],row["investor_count"],row["disclosed_count"],row["disclosed_amount_cny"],row["disclosed_count"]/row["event_count"] if row["event_count"] else None])
    for row in grade_stats:
        stats.append(["证据等级",row["label"],row["event_count"],None,None,None,None,None])
    stats.append(["并购", "全部并购候选",len(acquisitions),len({r["target_company_id"] for r in acquisitions}),None,sum(r["normalized_amount_cny"] is not None for r in acquisitions),sum(r["normalized_amount_cny"] or 0 for r in acquisitions),sum(r["normalized_amount_cny"] is not None for r in acquisitions)/len(acquisitions) if acquisitions else None])
    stats.append(["V1.1来源审计", "投资界新增候选（待人工审核）",len(v11_candidates),len({r["company_name_original"] for r in v11_candidates}),None,None,None,None])
    stats.append(["V1.1来源审计", "与V1.0重复",len(service.v11_candidates("duplicate_v1")),None,None,None,None,None])
    sheets = {
        "融资事件明细": matrix(funding,[("event_id","event_id"),("announcement_date","披露日期"),("transaction_date","交易日期"),("company_name","企业名称"),("primary_category","一级产业方向"),("secondary_track","二级赛道"),("financing_type","融资类型"),("round_original","融资轮次原文"),("normalized_round","标准化轮次"),("amount_original","融资金额原文"),("normalized_amount_cny","统一金额CNY"),("investors","投资方"),("use_of_funds_original","资金用途"),("source_title","原始新闻标题"),("source_url","来源URL"),("evidence_grade","证据等级"),("review_status","核验状态")]),
        "并购事件明细": matrix(acquisitions,[("acquisition_id","acquisition_id"),("disclosure_date","披露日期"),("transaction_date","交易日期"),("buyer_name_original","收购方"),("target_name_original","被收购方"),("transaction_type","交易类型"),("transaction_status","交易状态"),("amount_original","交易金额原文"),("normalized_amount_cny","统一金额CNY"),("primary_category","一级产业方向"),("secondary_track","二级赛道"),("rationale_original","交易依据"),("source_title","原始新闻标题"),("source_url","来源URL"),("evidence_grade","证据等级"),("verification_status","核验状态")]),
        "企业技术信息": matrix(profiles,[("company_id","company_id"),("company_name","企业名称"),("primary_category","一级产业方向"),("secondary_track","二级赛道"),("primary_business","企业主营业务"),("core_products","核心产品"),("core_technologies","核心技术"),("application_scenarios","应用场景"),("value_chain_position","产业链位置"),("technical_problem","技术问题"),("funding_use","资金用途"),("cross_domain_tags","跨领域标签"),("verification_status","技术信息可信度")]),
        "技术关键词库": matrix(keywords,[("keyword_id","keyword_id"),("raw_keyword","原始关键词"),("normalized_keyword","标准化关键词"),("description","技术说明"),("primary_category","一级产业方向"),("companies","涉及企业"),("event_ids","相关融资事件"),("source_urls","来源链接"),("verification_status","核验状态")]),
        "候选主题库": matrix(themes,[("theme_id","candidate_id"),("provisional_description","暂定技术描述"),("final_name","最终主题名称"),("primary_category","所属一级产业"),("companies","涉及企业"),("event_count","融资事件数量"),("disclosed_amount_cny","已披露融资金额合计"),("investor_count","参与投资机构数量"),("keywords","技术关键词"),("value_chain_position","产业链位置"),("formation_basis","形成依据"),("boundary_definition","主题边界"),("review_questions","待人工审核问题"),("review_status","人工审核状态")]),
        "数据来源与核验记录": matrix(sources,[("document_id","document_id"),("title","原始网页标题"),("source_name","来源名称"),("original_url","来源URL"),("published_at","发布日期"),("fetched_at","采集时间"),("evidence_default_grade","证据等级"),("fetch_status","访问状态"),("financing_category","交易类别"),("review_status","核验状态")]),
        "月度统计": stats,
    }
    payload = {"title":"2026年11月中国科技产业早期融资与并购样本库 V1.1","cutoff":"2026-11-25","coverage_complete":False,"sheets":sheets}
    (ROOT/"work"/"november_workbook_data.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({name:len(data)-1 for name,data in sheets.items()},ensure_ascii=False))


if __name__ == "__main__": main()
