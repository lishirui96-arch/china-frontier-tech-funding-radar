from __future__ import annotations
import json,sqlite3,uuid
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate
NS=uuid.UUID("b70df738-58bd-4de8-a2e2-e0b19e601e40")
def uid(x):return str(uuid.uuid5(NS,x))
def now():return datetime.now(timezone.utc).isoformat()
MERGE_NAMES={
frozenset(("卫星载荷与定量遥感数据链","卫星载荷与遥感数据服务")):"卫星载荷与遥感数据系统",
frozenset(("固态电池关键材料","固态电池电解质材料")):"固态电池电解质与关键材料"}
SPECIAL={
"AI算力与模型运行基础设施":("暂缓","需先移除启明光子的错误基础设施关联，再确认主题边界"),
"机器人关节执行与高密度机电集成":("暂缓","深圳华盛技术业务和产品仍待补充，暂不满足全部成员有产品级依据"),
"深空动力与任务系统观察项":("暂缓","三家企业画像仍不足以证明共同的深空动力或任务系统技术"),
"其他功能材料观察项":("继续拆分","四家企业材料类型和应用场景不同，现有证据不支持统一主题")}
def snapshot(c,tid):
    topic=dict(c.execute("""select t.*,i.name industry,f.name field from v22_topics t join v22_fields f using(field_id) join v22_industries i using(industry_id) where t.topic_id=?""",(tid,)).fetchone())
    companies=[dict(r) for r in c.execute("""select cp.company_id,cp.display_name,p.primary_business,l.product_basis,l.technology_basis,l.evidence_basis from v22_company_topic_links l join v22_companies cp using(company_id) join v22_company_profiles p using(company_id) where l.topic_id=?""",(tid,))]
    events=[dict(r) for r in c.execute("""select e.* from v22_event_topics x join v22_events e using(event_id) where x.topic_id=?""",(tid,))]
    return topic,companies,events
def main():
    migrate();c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row;ts=now()
    with c:
      for table in ("v23_merge_previews","v23_review_cards"):c.execute(f"delete from {table}")
      topics=[dict(r) for r in c.execute("select * from v22_topics")]
      duplicate_topics={r["left_topic_id"] for r in c.execute("select * from v22_topic_relations where relation_type='conceptual_duplicate'")}|{r["right_topic_id"] for r in c.execute("select * from v22_topic_relations where relation_type='conceptual_duplicate'")}
      for t in topics:
        topic,members,events=snapshot(c,t["topic_id"]);missing=[m["display_name"] for m in members if m["product_basis"]=="待补充" or m["technology_basis"]=="待补充"]
        if t["topic_id"] in duplicate_topics:rec,reason="合并","与另一来源候选表达同一技术问题，先查看合并预览"
        elif t["candidate_name"] in SPECIAL:rec,reason=SPECIAL[t["candidate_name"]]
        elif t["management_status"]=="A_multi_company_proposed" and not missing:rec,reason="建议确认正式主题","至少两家企业且成员产品、技术字段均有现有材料支持，仍需用户确认名称与边界"
        elif t["management_status"]=="A_multi_company_proposed":rec,reason="暂缓",f"{len(missing)}家成员缺少产品或技术依据："+"、".join(missing)
        elif t["management_status"]=="B_observation" and not missing:rec,reason="保留观察项","技术方向明确但当前仅一家企业，不进入多企业主题排名"
        elif t["management_status"]=="B_observation":rec,reason="暂缓观察",f"单企业画像证据不足：{'、'.join(missing)}"
        else:rec,reason="继续拆分","成员技术共同性不足"
        common="；".join(sorted({m["technology_basis"] for m in members if m["technology_basis"]!="待补充"})) or "待补充"
        value="具备独立研究价值，待人工确认" if rec in ("建议确认正式主题","保留观察项") else "需先解决成员证据、重复或边界问题"
        dup="存在概念重复" if t["topic_id"] in duplicate_topics else "未发现V2.2登记的概念重复"
        c.execute("insert into v23_review_cards values (?,?,?,?,?,?,?,?,?,?,?)",(uid("card:"+t["topic_id"]),t["topic_id"],t["management_status"],rec,reason,common,value,dup,json.dumps(members,ensure_ascii=False),json.dumps(events,ensure_ascii=False),ts))
      for rel in c.execute("select * from v22_topic_relations where relation_type='conceptual_duplicate'"):
        lt,lc,le=snapshot(c,rel["left_topic_id"]);rt,rc,re=snapshot(c,rel["right_topic_id"]);name=MERGE_NAMES[frozenset((lt["candidate_name"],rt["candidate_name"]))]
        company_ids={x["company_id"] for x in lc+rc};event_ids={x["event_id"] for x in le+re}
        diff={"shared_companies":len({x['company_id'] for x in lc}&{x['company_id'] for x in rc}),"shared_events":len({x['event_id'] for x in le}&{x['event_id'] for x in re}),"left_only_companies":[x['display_name'] for x in lc if x['company_id'] not in {y['company_id'] for y in rc}],"right_only_companies":[x['display_name'] for x in rc if x['company_id'] not in {y['company_id'] for y in lc}]}
        c.execute("insert into v23_merge_previews values (?,?,?,?,?,?,?,?,?,?)",(uid("preview:"+rel["relation_id"]),rel["left_topic_id"],rel["right_topic_id"],name,json.dumps({"topic":lt,"companies":lc,"events":le},ensure_ascii=False),json.dumps({"topic":rt,"companies":rc,"events":re},ensure_ascii=False),len(company_ids),len(event_ids),json.dumps(diff,ensure_ascii=False),"pending"))
    print(json.dumps({"cards":c.execute('select count(*) from v23_review_cards').fetchone()[0],"multi":c.execute("select count(*) from v23_review_cards where candidate_class='A_multi_company_proposed'").fetchone()[0],"observations":c.execute("select count(*) from v23_review_cards where candidate_class='B_observation'").fetchone()[0],"split":c.execute("select count(*) from v23_review_cards where candidate_class='C_needs_further_split'").fetchone()[0],"merge_previews":c.execute('select count(*) from v23_merge_previews').fetchone()[0],"formal_directory":c.execute('select count(*) from v23_formal_topics').fetchone()[0]},ensure_ascii=False));c.close()
if __name__=="__main__":main()
