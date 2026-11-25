from __future__ import annotations

import json, sqlite3, uuid
from datetime import datetime, timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate

NS=uuid.UUID("78170e60-914e-4f66-a387-f995ec690fd7")
MULTI={"金领生物":["天使轮","天使+轮"],"稳准智能":["A轮","A+轮"],"通芯智能":["种子轮","天使轮"],"途深智合":["Pre-A轮","Pre-A+轮"],"观测云":["A轮","A+轮"],"北辰航天":["Pre-A+轮","A轮"],"瑞启深空":["天使轮","天使+轮"],"谱星航天":["Pre-A轮","A轮"]}
MEDIA_CONFLICT={"蓝固新能源","赛恩领动","天链测控","英伟芯"}
NAME_FOCUS={"无涯智远（Norizon AI）","优理奇机器人（UniX AI）","金领生物","北辰航天","稳准智能","英伟芯","赛恩领动","通芯智能","谱星航天","途深智合","蓝固新能源","观测云","天链测控"}

def uid(s): return str(uuid.uuid5(NS,s))
def now(): return datetime.now(timezone.utc).isoformat()

def main():
    migrate(); con=sqlite3.connect(database_path()); con.row_factory=sqlite3.Row; ts=now()
    audits=[dict(x) for x in con.execute("select * from v13_candidate_quality_audits order by normalized_disclosure_date,normalized_company_name")]
    duplicate_secondary={x["right_audit_id"]:dict(x) for x in con.execute("select * from v13_candidate_relations where relation_type='confirmed_duplicate'")}
    multi_seen=set()
    with con:
        for table in ("v14_review_actions","v14_duplicate_decisions","v14_round_adjudications","v14_company_revisions","v14_event_units"):
            con.execute(f"delete from {table}")
        for a in audits:
            name=a["normalized_company_name"]
            if a["audit_id"] in duplicate_secondary:
                eligibility,reason,structure="C_excluded","同一融资事件的重复来源报道；保留来源但不重复计数","duplicate_source"
            elif name in MULTI or name in MEDIA_CONFLICT or a["overall_verification_status"] in ("pending","conflict"):
                eligibility,reason,structure="B_pending","轮次或事件结构尚需人工裁决，不计入正式统计","split_recommended" if name in MULTI else "conflict_pending"
            elif a["evidence_grade"] in ("S","A","B"):
                eligibility,reason,structure="A_statistical","融资事实、企业简称、轮次及披露日期具备公开来源支持，且无重大重复或轮次冲突","single"
            else:
                eligibility,reason,structure="B_pending","来源或关键字段证据不足，保留待核验","conflict_pending"
            rounds=MULTI.get(name,[a["normalized_round"]])
            if structure=="split_recommended":
                if name in multi_seen: structure="conflict_pending"
                else: multi_seen.add(name)
            # Keep one prepared unit per source candidate. Proposed splits remain recommendations until human confirmation.
            canonical=uid("event:"+(duplicate_secondary.get(a["audit_id"],{}).get("left_audit_id") or a["audit_id"]))
            unit=uid("unit:"+a["audit_id"])
            con.execute("insert into v14_event_units values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(unit,a["audit_id"],a["company_id"],canonical,1,name,a["normalized_round"],a["normalized_disclosure_date"],a["normalized_amount"],a["normalized_investors"],eligibility,reason,structure,"automated_preparation",1,ts,ts))
            if name in MULTI:
                kind,basis,rec,status="C_distinct_rounds",f"原文标题明确并列披露 {'、'.join(rounds)}；各轮应保留独立事件ID，但需人工确认各轮日期、金额和投资方",f"建议拆分为 {len(rounds)} 个事件单元：{'、'.join(rounds)}","pending_human_review"
            elif name in MEDIA_CONFLICT:
                kind,basis,rec,status="E_media_conflict",f"现有来源对轮次表述不一致或仅称系列融资：{a['original_round']}","保持单条待审，不自动拆分或合并","pending_human_review"
            elif a["overall_verification_status"]=="conflict":
                kind,basis,rec,status="F_unresolved","现有证据不足以判断历史轮次、本轮融资或分阶段交割","进入人工审核队列","pending_human_review"
            else: kind=None
            if kind:
                con.execute("insert into v14_round_adjudications values (?,?,?,?,?,?,?,?,?)",(uid("round:"+a["audit_id"]),a["audit_id"],kind,a["original_round"],json.dumps(rounds,ensure_ascii=False),basis,rec,status,ts))
            if name in NAME_FOCUS or a["name_quality_status"]!="accurate":
                entity=con.execute("select * from v13_company_entities where company_id=?",(a["company_id"],)).fetchone()
                status="confirmed_display_name" if name.endswith("）") or a["name_quality_status"] in ("accurate","corrected") else "pending_name_review"
                if not entity["official_name"]: status="pending_legal_entity"
                con.execute("insert into v14_company_revisions values (?,?,?,?,?,?,?,?,?,?,?)",(uid("company:"+a["audit_id"]),a["company_id"],a["audit_id"],a["original_company_name"],name,entity["official_name"],entity["english_name"],status,"标准化名称由原文标题确认；法定主体仅在有可靠公开证据时填写",a["source_url"],ts))
        for r in con.execute("select * from v13_candidate_relations where relation_type='confirmed_duplicate'").fetchall():
            con.execute("insert into v14_duplicate_decisions values (?,?,?,?,?,?,?,?)",(uid("duplicate:"+r["relation_id"]),r["relation_id"],uid("event:"+r["left_audit_id"]),uid("event:"+r["right_audit_id"]),"merge_sources",r["basis"]+"；以左侧审计记录建立主事件，右侧作为附加来源","prepared",ts))
    print(json.dumps({"units":con.execute("select count(*) from v14_event_units").fetchone()[0],"A":con.execute("select count(*) from v14_event_units where sample_eligibility_status='A_statistical'").fetchone()[0],"B":con.execute("select count(*) from v14_event_units where sample_eligibility_status='B_pending'").fetchone()[0],"C":con.execute("select count(*) from v14_event_units where sample_eligibility_status='C_excluded'").fetchone()[0],"round_adjudications":con.execute("select count(*) from v14_round_adjudications").fetchone()[0],"company_revisions":con.execute("select count(*) from v14_company_revisions").fetchone()[0]},ensure_ascii=False)); con.close()

if __name__=="__main__": main()
