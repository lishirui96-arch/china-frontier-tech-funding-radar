from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from funding_radar.db import database_path


ROOT=Path(__file__).resolve().parents[1]
NS=uuid.UUID("be5d83af-3992-4b93-a3ab-98f7c20926fd")
MEDIA_DOMAINS=("pedaily.cn","36kr.com","chinaventure.com.cn","cls.cn","qq.com","sohu.com","msn.cn","sina.com.cn","163.com")
CORRECTIONS={
    "无涯智远（Norizon AI":"无涯智远（Norizon AI）","优理奇机器人（UniX AI":"优理奇机器人（UniX AI）",
    "AI-native 芯片设计平台NovaSilicon":"NovaSilicon","后摩智能低调":"后摩智能",
    "理想系”至简动力已":"至简动力","字节跳动再度领投！云脉芯联":"云脉芯联",
    "合肥幺正量子":"幺正量子","谱星航天连续":"谱星航天","固态电池材料巨头":"蓝固新能源",
    "瑞启深空三个月内":"瑞启深空","Chenghengwei":"诚恒微",
}
ROUND_CONFLICT_NAMES={"金领生物","稳准智能","通芯智能","途深智合","观测云","北辰航天","英伟芯","赛恩领动","天链测控","瑞启深空","蓝固新能源","谱星航天"}


def uid(value:str)->str:return str(uuid.uuid5(NS,value))
def now()->str:return datetime.now(timezone.utc).isoformat()
def compact(value:str)->str:return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+","",value or "").lower()


def category(title:str)->tuple[str,str]:
    rules=[("机器人与具身智能",r"机器人|具身|灵巧手|脑机"),("半导体与先进封装",r"芯片|半导体|SoC|RISC-V|封装|光互连"),("量子信息与先进计算",r"量子"),("新能源与新材料",r"电池|能源|材料|电解质|磁材"),("生物制造与生命科技",r"生物|医药|医疗|细胞|蛋白|ADC|药物|基因"),("商业航天与低空经济",r"航天|航空|卫星|eVTOL|无人机"),("人工智能与AI基础设施",r"AI|人工智能|大模型|数据|智能")]
    for primary,pattern in rules:
        if re.search(pattern,title,re.I):return primary,re.search(pattern,title,re.I).group(0)
    return "其他新兴技术方向","待分类"


def legal_name(text:str,short_name:str)->str|None:
    if not text or not short_name:return None
    core=re.sub(r"[（(].*?[）)]","",short_name)
    for match in re.finditer(r"[\u4e00-\u9fffA-Za-z0-9（）()]{4,55}(?:股份有限公司|有限责任公司|有限公司)",text):
        value=match.group(0)
        if core[:2] and core[:2] in value:return value[-55:]
    return None


def main()->None:
    con=sqlite3.connect(database_path());con.row_factory=sqlite3.Row;timestamp=now()
    v11=[dict(r) for r in con.execute("""SELECT c.candidate_id,c.company_name_original,c.disclosure_date,c.round_original,c.round_normalized,c.amount_original,
        c.evidence_grade,c.unresolved_fields,d.title,d.original_url,d.text_or_summary,a.original_access_status
        FROM v11_funding_candidates c JOIN raw_documents d ON d.document_id=c.source_document_id
        LEFT JOIN source_document_audit a USING(document_id) WHERE c.candidate_status='verified_new'""")]
    v12=[dict(r) for r in con.execute("SELECT * FROM v12_funding_candidates WHERE candidate_status='new'")]
    existing_companies=[dict(r) for r in con.execute("SELECT * FROM companies")]
    items=[]
    for r in v11:
        primary,secondary=category(r["title"])
        items.append({"version":"V1.1","id":r["candidate_id"],"name":r["company_name_original"],"date":r["disclosure_date"],"round":r["round_original"],"round_normalized":r["round_normalized"],"amount":r["amount_original"],"investors":"未结构化提取","primary":primary,"secondary":secondary,"title":r["title"],"url":r["original_url"],"grade":r["evidence_grade"],"text":r.get("text_or_summary") or "","access":r.get("original_access_status") or "accessible"})
    for r in v12:
        text=""
        source=con.execute("SELECT raw_json,original_access_status FROM v12_source_records WHERE source_record_id=?",(r.get("source_record_id"),)).fetchone() if r.get("source_record_id") else None
        if source:text=source["raw_json"]
        items.append({"version":"V1.2","id":r["candidate_id"],"name":r["company_name_original"],"date":r["disclosure_date"],"round":r["round_original"],"round_normalized":r["round_normalized"],"amount":r["amount_original"],"investors":r["investors_original"],"primary":r["primary_category"],"secondary":r["secondary_track"],"title":r["source_title"],"url":r["original_url"],"grade":r["evidence_grade"],"text":text,"access":"accessible" if r["verification_status"] in ("verified","partially_verified") else "pending"})

    with con:
        for table in ("v13_field_verifications","v13_candidate_relations","v13_official_evidence","v13_change_history","v13_acquisition_verifications","v13_candidate_quality_audits","v13_company_entities"):
            con.execute(f"DELETE FROM {table}")
        audit_rows=[]
        for item in items:
            original=item["name"]; normalized=CORRECTIONS.get(original,original).strip(" ：:（）()\"' ")
            issues=[]
            if original!=normalized:issues.append("企业名称含标题前缀、截断或描述词，已保留原值并建立标准化名称")
            if re.search(r"低调|连续$|三个月内$|巨头$|领投|平台",original):issues.append("企业名称疑似混入新闻描述")
            if original.count("（")!=original.count("）"):issues.append("企业名称括号截断")
            if item["round"] in ("A轮、A+轮","种子轮、天使轮") or normalized in ROUND_CONFLICT_NAMES:issues.append("单条披露含多轮融资或来源间轮次冲突，需拆分/复核")
            legal=None
            for company in existing_companies:
                if normalized and (compact(normalized) in compact(company["official_name"]) or compact(normalized)==compact(company.get("short_name") or "")):
                    legal=company["official_name"] if any(x in company["official_name"] for x in ("有限公司","股份有限公司")) else None;break
            legal=legal or legal_name(item["text"],normalized)
            entity_id=uid("company:"+compact(normalized))
            business=item["title"].split("，",1)[1][:240] if "，" in item["title"] else "待核实"
            entity_status="partially_verified" if legal else "pending"
            con.execute("INSERT OR IGNORE INTO v13_company_entities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(entity_id,legal,normalized,None,None,None,None,business,"待核实",item["primary"],item["secondary"],entity_status,json.dumps([item["url"]],ensure_ascii=False),timestamp,timestamp))
            audit_id=uid(f"audit:{item['version']}:{item['id']}")
            name_status="corrected" if original!=normalized else ("suspected_error" if issues else "accurate")
            round_conflict=any("轮次" in x for x in issues)
            field_status={
                "event_verified":"verified" if item["grade"] in ("S","A","B") and item["access"]=="accessible" else "partially_verified",
                "company_verified":"partially_verified" if legal else "pending",
                "round_verified":"conflict" if round_conflict else ("verified" if item["round"] and item["round"] in item["title"] else "partially_verified"),
                "amount_verified":"verified" if item["amount"] not in ("未披露","None","") and item["amount"].replace(" ","") in item["title"].replace(" ","") else ("partially_verified" if item["amount"] not in ("未披露","None","") else "pending"),
                "investor_verified":"partially_verified" if item["investors"] not in ("未结构化提取","[]","",None) else "pending",
                "date_verified":"verified" if item["access"]=="accessible" else "partially_verified",
                "source_verified":"verified" if item["access"]=="accessible" else "partially_verified",
            }
            values=list(field_status.values())
            overall="conflict" if "conflict" in values else ("complete" if all(x=="verified" for x in values) else ("partial" if field_status["event_verified"]=="verified" and field_status["source_verified"]=="verified" else "pending"))
            con.execute("INSERT INTO v13_candidate_quality_audits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                audit_id,item["version"],item["id"],entity_id,original,normalized,item["date"],item["date"],item["round"],item["round_normalized"],item["amount"],item["amount"],item["investors"],item["investors"],item["primary"],item["primary"],item["secondary"],item["secondary"],item["title"],item["url"],item["grade"],name_status,json.dumps(issues,ensure_ascii=False),overall,timestamp,"规则审计+原文/多来源比对"))
            for field,status in field_status.items():
                excerpt={"event_verified":"原文明确披露融资事实","company_verified":"媒体简称不能自动证明法定主体","round_verified":f"原始轮次：{item['round']}","amount_verified":f"原始金额：{item['amount']}","investor_verified":f"原始投资方：{item['investors']}","date_verified":"当前仅核实公开披露日期，非实际交割日期","source_verified":f"来源访问状态：{item['access']}"}[field]
                con.execute("INSERT INTO v13_field_verifications VALUES (?,?,?,?,?,?,?,?,?)",(uid(f"field:{audit_id}:{field}"),audit_id,field,status,json.dumps([item["url"]],ensure_ascii=False),excerpt,"原文与结构化字段比对","automated_v1.3_audit",timestamp))
            if original!=normalized:
                con.execute("INSERT INTO v13_change_history VALUES (?,?,?,?,?,?,?,?,?,?)",(uid(f"change:{audit_id}:name"),"funding_candidate",audit_id,"company_name",original,normalized,"修复标题前缀、括号截断或描述词污染",item["url"],"automated_v1.3_audit",timestamp))
            con.execute("INSERT INTO v13_official_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(uid(f"official:{audit_id}"),audit_id,None,"not_found","未发现可确认的官方发布",item["title"],item["url"],item["access"],"[]",item["grade"],"当前来源为媒体或聚合来源；未据此升级企业法定主体、交割日期或投资方角色。",timestamp))
            audit_rows.append({"audit_id":audit_id,"name":normalized,"date":item["date"],"round":item["round"],"title":item["title"]})
        for i,left in enumerate(audit_rows):
            for right in audit_rows[i+1:]:
                if left["name"]!=right["name"]:continue
                day_gap=abs((datetime.fromisoformat(left["date"])-datetime.fromisoformat(right["date"])).days)
                if day_gap<=3 and left["round"]==right["round"]:
                    relation,basis,status,confidence="confirmed_duplicate","同一标准化企业、相同轮次、披露日期接近，属于同轮多来源报道","resolved",0.96
                elif day_gap<=3 and ("连续" in left["title"]+right["title"] or "两轮" in left["title"]+right["title"] or left["name"] in {"谱星航天","蓝固新能源","至简动力","幺正量子"}):
                    relation,basis,status,confidence="uncertain","同一企业和接近日期但轮次不一致；可能为多轮合并披露或来源分类错误","pending_human_review",0.75
                else:
                    relation,basis,status,confidence="confirmed_distinct","同一企业但日期或轮次不同，当前保留为不同事件","resolved",0.85
                con.execute("INSERT INTO v13_candidate_relations VALUES (?,?,?,?,?,?,?,?)",(uid(f"relation:{left['audit_id']}:{right['audit_id']}:{relation}"),left["audit_id"],right["audit_id"],relation,confidence,basis,status,timestamp))
        acquisitions=[dict(r) for r in con.execute("""SELECT acquisition_id acquisition_key,'V1.0' origin,buyer_name_original buyer,target_name_original target,
            disclosure_date,amount_original,transaction_status,evidence_grade,verification_status FROM acquisition_events""")]
        acquisitions += [dict(r) for r in con.execute("""SELECT acquisition_candidate_id acquisition_key,'V1.2' origin,buyer_name buyer,target_name target,
            disclosure_date,amount_original,transaction_status,evidence_grade,verification_status FROM v12_acquisition_candidates""")]
        for row in acquisitions:
            if row["origin"]=="V1.0":
                urls=[x[0] for x in con.execute("SELECT d.original_url FROM acquisition_documents ad JOIN raw_documents d USING(document_id) WHERE ad.acquisition_id=?",(row["acquisition_key"],))]
            else:
                urls=[x[0] for x in con.execute("SELECT source_url FROM v12_acquisition_candidates WHERE acquisition_candidate_id=?",(row["acquisition_key"],))]
            board="announced_or_reviewed" if row["transaction_status"] in ("announced","in_progress") else "pending"
            con.execute("INSERT INTO v13_acquisition_verifications VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
                uid("ma-verify:"+row["acquisition_key"]),row["acquisition_key"],row["origin"],row["buyer"],row["target"],"原记录见交易明细",row["amount_original"],row["disclosure_date"],board,"pending","pending","not_completed" if row["transaction_status"]!="completed" else "completed",row["evidence_grade"],"partially_verified" if urls else "pending",json.dumps(urls,ensure_ascii=False),"股东大会、监管审批及最终交割状态需继续以公告核验",timestamp))
    stats={"audits":con.execute("SELECT COUNT(*) FROM v13_candidate_quality_audits").fetchone()[0],"entities":con.execute("SELECT COUNT(*) FROM v13_company_entities").fetchone()[0],"field_checks":con.execute("SELECT COUNT(*) FROM v13_field_verifications").fetchone()[0],"relations":con.execute("SELECT COUNT(*) FROM v13_candidate_relations").fetchone()[0],"name_corrections":con.execute("SELECT COUNT(*) FROM v13_change_history WHERE field_name='company_name'").fetchone()[0],"acquisitions":con.execute("SELECT COUNT(*) FROM v13_acquisition_verifications").fetchone()[0]}
    con.close();print(json.dumps(stats,ensure_ascii=False))


if __name__=="__main__":main()
