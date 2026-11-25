from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from funding_radar.db import database_path


ROOT=Path(__file__).resolve().parents[1];DOCS=ROOT/"docs"


def write_csv(path:Path,rows:list[dict])->None:
    fields=list(rows[0]) if rows else ["status"]
    with path.open("w",encoding="utf-8-sig",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main()->None:
    con=sqlite3.connect(database_path());con.row_factory=sqlite3.Row
    audits=[dict(r) for r in con.execute("""SELECT q.*,e.official_name,e.short_name,e.english_name,e.unified_social_credit_code,e.registered_location,e.official_website,
        e.primary_business,e.core_products,e.verification_status entity_verification_status FROM v13_candidate_quality_audits q JOIN v13_company_entities e USING(company_id)
        ORDER BY q.normalized_disclosure_date DESC,q.normalized_company_name""")]
    entities=[dict(r) for r in con.execute("SELECT * FROM v13_company_entities ORDER BY short_name")]
    fields=[dict(r) for r in con.execute("""SELECT f.*,q.candidate_version,q.source_candidate_id,q.normalized_company_name,q.normalized_disclosure_date,q.normalized_round
        FROM v13_field_verifications f JOIN v13_candidate_quality_audits q USING(audit_id) ORDER BY q.normalized_disclosure_date DESC,q.normalized_company_name,f.field_name""")]
    relations=[dict(r) for r in con.execute("""SELECT x.*,l.normalized_company_name left_company,l.normalized_disclosure_date left_date,l.normalized_round left_round,
        r.normalized_company_name right_company,r.normalized_disclosure_date right_date,r.normalized_round right_round
        FROM v13_candidate_relations x JOIN v13_candidate_quality_audits l ON l.audit_id=x.left_audit_id
        JOIN v13_candidate_quality_audits r ON r.audit_id=x.right_audit_id ORDER BY l.normalized_company_name,l.normalized_disclosure_date""")]
    official=[dict(r) for r in con.execute("""SELECT o.*,q.normalized_company_name,q.normalized_disclosure_date,q.normalized_round
        FROM v13_official_evidence o LEFT JOIN v13_candidate_quality_audits q USING(audit_id) ORDER BY q.normalized_company_name""")]
    changes=[dict(r) for r in con.execute("SELECT * FROM v13_change_history ORDER BY changed_at,entity_id")]
    acquisitions=[dict(r) for r in con.execute("SELECT * FROM v13_acquisition_verifications ORDER BY first_announcement_date DESC,buyer_name")]
    con.close()
    write_csv(DOCS/"NOVEMBER_2026_V1_3_CANDIDATE_QUALITY_ISSUES.csv",audits)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_COMPANY_ENTITY_MASTER.csv",entities)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_FIELD_VERIFICATIONS.csv",fields)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_DUPLICATE_CONFLICTS.csv",relations)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_OFFICIAL_EVIDENCE.csv",official)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_CHANGE_HISTORY.csv",changes)
    write_csv(DOCS/"NOVEMBER_2026_V1_3_ACQUISITION_VERIFICATIONS.csv",acquisitions)
    name_counts=Counter(x["name_quality_status"] for x in audits);overall=Counter(x["overall_verification_status"] for x in audits);grades=Counter(x["evidence_grade"] for x in audits)
    field_count={(x["field_name"],x["verification_status"]):0 for x in fields}
    for x in fields:field_count[(x["field_name"],x["verification_status"])]+=1
    duplicate_count=sum(x["relation_type"]=="confirmed_duplicate" for x in relations)
    conflict_count=field_count.get(("round_verified","conflict"),0)
    legal_candidates=sum(bool(x["official_name"]) for x in entities)
    official_verified=sum(x["verification_status"]=="verified" for x in entities)
    (DOCS/"NOVEMBER_2026_V1_3_QUALITY_AUDIT_REPORT.md").write_text(f"""# 融资雷达 V1.3 候选质量审计报告

审计对象：V1.1新增72条与V1.2新增29条，共101条独立待审候选。所有结果保留原始值、标准化值和变更历史；未写入正式融资事件表。

## 核心统计

| 指标 | 数量 |
|---|---:|
| 企业名称完全准确 | {name_counts['accurate']} |
| 企业名称已修正 | {name_counts['corrected']} |
| 企业名称仍疑似错误 | {name_counts['suspected_error']} |
| 企业法定名称候选（媒体支持） | {legal_candidates} |
| 企业法定名称官方核实 | {official_verified} |
| 已确认重复关系 | {duplicate_count} |
| 存在轮次冲突/多轮合并 | {conflict_count} |
| 融资金额已核实 | {field_count.get(('amount_verified','verified'),0)} |
| 投资方已核实 | {field_count.get(('investor_verified','verified'),0)} |
| 投资方部分核实 | {field_count.get(('investor_verified','partially_verified'),0)} |
| 披露日期已核实 | {field_count.get(('date_verified','verified'),0)} |
| 完整核实事件 | {overall['complete']} |
| 部分核实事件 | {overall['partial']} |
| 待核实事件 | {overall['pending']} |
| 存在冲突事件 | {overall['conflict']} |

证据等级：S={grades['S']}、A={grades['A']}、B={grades['B']}、C={grades['C']}、D={grades['D']}。

## 主要问题

- 10条名称已建立原值到标准化值的修正记录；另有13条仍含描述词、品牌/主体不清或标题截断风险。
- 至简动力、幺正量子、诚恒微和谱星航天的同轮多来源记录已建立确认重复关系，所有来源继续保留。
- 谱星航天、蓝固新能源等来源间轮次不一致；金领生物、稳准智能、通芯智能、途深智合、观测云等单篇披露包含多轮融资，保留冲突并等待人工拆分。
- 媒体可以确认融资披露事实，但不能单独证明法定主体、实际交割日和投资方角色。当前没有候选满足全部字段均为已核实，因此完整核实数为0。
""",encoding="utf-8")
    ma_lines="\n".join(f"| {x['buyer_name']} | {x['target_name']} | {x['first_announcement_date']} | {x['amount_original']} | {x['board_status']} | {x['shareholder_status']} | {x['regulatory_status']} | {x['closing_status']} | {x['evidence_grade']} | {x['verification_status']} |" for x in acquisitions)
    (DOCS/"NOVEMBER_2026_V1_3_ACQUISITION_VERIFICATION_REPORT.md").write_text(f"""# V1.3 并购专项核验报告

8条并购候选均与融资候选分表存储。媒体报道不作为交易完成证据；未见交割完成公告的交易统一保留为未完成/待核验。

| 收购方 | 标的方 | 首次公告日 | 对价 | 董事会 | 股东大会 | 监管审批 | 交割 | 等级 | 核验状态 |
|---|---|---|---|---|---|---|---|---|---|
{ma_lines}

新增两条艾为电子/钰泰半导体、斯菱智驱/银球科技目前仍为B级媒体线索。尚未取得可直接确认董事会、股东大会、监管和交割状态的交易所原始文件，因此未标记为完成交易。
""",encoding="utf-8")
    summary=[["指标","数量"],["候选总数",len(audits)],["企业实体",len(entities)],["名称准确",name_counts['accurate']],["名称修正",name_counts['corrected']],["名称疑似错误",name_counts['suspected_error']],["确认重复",duplicate_count],["轮次冲突",conflict_count],["完整核实",overall['complete']],["部分核实",overall['partial']],["待核实",overall['pending']],["存在冲突",overall['conflict']]]
    workbook={"title":"融资雷达 V1.3 候选事件质量审计","cutoff":"2026-11-25","sheets":{
        "质量审计汇总":summary,
        "101条候选审计":[list(audits[0]),*[list(x.values()) for x in audits]],
        "企业实体主表":[list(entities[0]),*[list(x.values()) for x in entities]],
        "字段级核验":[list(fields[0]),*[list(x.values()) for x in fields]],
        "重复与冲突":[list(relations[0]),*[list(x.values()) for x in relations]],
        "官方证据状态":[list(official[0]),*[list(x.values()) for x in official]],
        "并购专项核验":[list(acquisitions[0]),*[list(x.values()) for x in acquisitions]],
    }}
    (ROOT/"work"/"v13_workbook_data.json").write_text(json.dumps(workbook,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"audits":len(audits),"entities":len(entities),"accurate":name_counts['accurate'],"corrected":name_counts['corrected'],"suspected":name_counts['suspected_error'],"duplicates":duplicate_count,"round_conflicts":conflict_count,"complete":overall['complete'],"partial":overall['partial'],"pending":overall['pending'],"conflict":overall['conflict']},ensure_ascii=False))


if __name__=="__main__":main()
