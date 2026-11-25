from __future__ import annotations
import json,sqlite3,uuid,re
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate
NS=uuid.UUID("96a5d69b-8090-4a2a-af23-c857402b758f")
def uid(x):return str(uuid.uuid5(NS,x))
def now():return datetime.now(timezone.utc).isoformat()

INDUSTRIES=[
("01","机器人与具身智能",["具身智能与自主作业","机器人核心部件","机器人感知技术"]),
("02","AI计算与半导体",["AI芯片与端侧计算","AI算力基础设施","光电互连与先进计算","半导体装备与先进封装"]),
("03","AI软件与工业智能",["企业AI与智能体","工业智能与知识系统","大模型基础能力","AI驱动的决策与自动化"]),
("04","新能源与先进材料",["固态电池材料","新能源关键材料","高性能功能材料","磁性材料与功能涂层"]),
("05","高端装备与先进制造",["电池制造装备","增材制造","精密制造与加工装备","高端检测与工业装备"]),
("06","商业航天与卫星应用",["卫星载荷与遥感","商业航天基础设施","航天测控与地面服务","深空探测与任务系统"]),
("07","低空经济与无人系统",["无人机系统与低空运输","低空飞行器与动力系统","飞控、导航与低空管理"]),
("08","生物制造与生命科学",["AI驱动的生命科学","核酸药物","抗体与偶联药物","新型生物药","细胞治疗","生命科学仪器"]),
("09","脑科学与神经技术",["脑机接口","神经信号采集与处理","神经调控与康复"]),
("10","量子科技",["量子计算硬件","量子计算软件","量子精密测量"])]

def destination(name):
    rules=[
    (r"工业与室外|通用人形|具身",("01","具身智能与自主作业")),(r"关节执行",("01","机器人核心部件")),(r"视触觉",("01","机器人感知技术")),
    (r"端侧推理|存算一体",("02","AI芯片与端侧计算")),(r"算力与模型运行|专属AI云",("02","AI算力基础设施")),(r"光互连|硅光",("02","光电互连与先进计算")),
    (r"企业智能体",("03","企业AI与智能体")),(r"持续学习|自进化",("03","大模型基础能力")),
    (r"固态电池.*材料|固态电池电解质",("04","固态电池材料")),(r"磁性材料",("04","磁性材料与功能涂层")),(r"涂层",("04","磁性材料与功能涂层")),(r"功能材料",("04","高性能功能材料")),
    (r"电池.*装备",("05","电池制造装备")),(r"增材制造",("05","增材制造")),
    (r"卫星载荷|遥感",("06","卫星载荷与遥感")),(r"测运控|测控与地面",("06","航天测控与地面服务")),(r"深空",("06","深空探测与任务系统")),
    (r"无人机|低空",("07","无人机系统与低空运输")),
    (r"虚拟细胞|AI药物|RNA结构设计",("08","AI驱动的生命科学")),(r"核酸药物|RNA技术",("08","核酸药物")),(r"ADC|抗体偶联",("08","抗体与偶联药物")),(r"新型生物药载荷",("08","新型生物药")),(r"细胞工程|细胞治疗",("08","细胞治疗")),(r"临床检测|质谱|分析仪器",("08","生命科学仪器")),
    (r"脑机接口",("09","脑机接口")),(r"量子.*软件",("10","量子计算软件")),(r"量子.*传感|精密传感",("10","量子精密测量")),(r"量子计算硬件|原子光子",("10","量子计算硬件"))]
    for pat,dest in rules:
        if re.search(pat,name):return dest
    return None
def clean_name(name,recommendation,suggested):
    if suggested:return suggested
    aliases={"专属AI云与智能体基础设施":"AI算力与模型运行基础设施","中性原子与原子光子量子计算硬件":"多路线量子计算硬件与系统工程","高性能材料与增材制造量产体系":"增材制造材料、装备与批量交付"}
    return aliases.get(name,name)
def canonical(name):
    if re.search(r"卫星载荷.*遥感",name):return "satellite-remote-sensing"
    if re.search(r"固态电池.*(关键材料|电解质)",name):return "solid-state-battery-materials"
    return re.sub(r"观察项|其他|的|与|、|AI","",name).lower()

def main():
    migrate();c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row;ts=now()
    with c:
      for table in ("v22_event_topics","v22_event_companies","v22_events","v22_company_tags","v22_company_topic_links","v22_company_profiles","v22_companies","v22_topic_relations","v22_topic_history","v22_topics","v22_fields","v22_industries"):c.execute(f"delete from {table}")
      inds={};fields={}
      for order,(code,name,field_names) in enumerate(INDUSTRIES,1):
        iid=uid("industry:"+code);inds[code]=iid;c.execute("insert into v22_industries values (?,?,?,?,?)",(iid,code,name,order,"confirmed_by_user"))
        for j,field in enumerate(field_names,1):
          fid=uid("field:"+code+":"+field);fields[(code,field)]=fid;c.execute("insert into v22_fields values (?,?,?,?,?)",(fid,iid,field,j,"confirmed_by_user"))
      sources=[]
      for r in c.execute("""select t.topic_id source_ref,t.candidate_name source_name,t.technical_boundary,a.recommendation,a.suggested_name,t.topic_kind from v2_candidate_topics t join v21_topic_audits a using(topic_id) where a.recommendation<>'拆分'"""):
        name=clean_name(r["source_name"],r["recommendation"],r["suggested_name"]);status="B_observation" if r["topic_kind"]=="single_company_observation" else "A_multi_company_proposed";sources.append(dict(source_kind="retained_v2",source_ref=r["source_ref"],name=name,boundary=r["technical_boundary"],status=status))
      for r in c.execute("select * from v211_split_proposals"):
        status={"multi_company_candidate":"A_multi_company_proposed","single_company_observation":"B_observation","needs_manual_split":"C_needs_further_split"}[r["proposal_status"]]
        sources.append(dict(source_kind="split_v211",source_ref=r["proposal_id"],name=r["subtopic_name"],boundary=r["split_basis"],status=status))
      topic_by_source={};canonical_groups={}
      for src in sources:
        dest=destination(src["name"])
        if not dest:raise RuntimeError("No V2.2 destination for "+src["name"])
        tid=uid("topic-source:"+src["source_kind"]+":"+src["source_ref"]);topic_by_source[(src["source_kind"],src["source_ref"])]=tid;ckey=canonical(src["name"]);canonical_groups.setdefault(ckey,[]).append(tid)
        c.execute("insert into v22_topics values (?,?,?,?,?,?,?,?,?,?,?)",(tid,fields[dest],src["name"],src["boundary"],src["status"],"pending",src["source_kind"],src["source_ref"],ckey,ts,ts))
      for key,tids in canonical_groups.items():
        if len(tids)>1:
          for right in tids[1:]:c.execute("insert into v22_topic_relations values (?,?,?,?,?,?,?)",(uid("rel:"+tids[0]+right),tids[0],right,"conceptual_duplicate","建议合并","来源主题与拆分子组表达同一技术问题，保留两条来源记录等待人工确认","pending"))
      profiles=[dict(r) for r in c.execute("select r.*,p.evidence_urls_json from v211_profile_reviews r join v2_company_profiles p using(profile_id)")]
      company_by_profile={}
      for p in profiles:
        cid=uid("company:"+p["profile_id"]);company_by_profile[p["profile_id"]]=cid;c.execute("insert into v22_companies values (?,?,?,?,?)",(cid,p["profile_id"],p["suggested_name"],"duplicate_pending" if c.execute("select 1 from v211_entity_duplicate_checks where left_profile_id=? or right_profile_id=?",(p["profile_id"],p["profile_id"])).fetchone() else "active",ts))
        c.execute("insert into v22_company_profiles values (?,?,?,?,?,?,?,?,?,?,?,?)",(cid,p["suggested_business"],p["suggested_products"],p["suggested_technologies"],p["suggested_scenarios"],p["suggested_chain"],None,None,None,"unclassified","等待产品级主题依据",p["evidence_urls_json"]))
      # Retained-topic memberships use field-cleaned V2.1.1 links.
      for x in c.execute("select * from v211_product_technology_topic_links"):
        tid=topic_by_source.get(("retained_v2",x["topic_id"]))
        if not tid:continue
        role="cross" if x["topic_fit"] in ("secondary_cross_tag",) else "primary_candidate"
        c.execute("insert or ignore into v22_company_topic_links values (?,?,?,?,?,?,?)",(company_by_profile[x["profile_id"]],tid,role,x["product_basis"],x["technology_basis"],x["evidence_basis"],"pending"))
      # Split memberships have explicit product/technology basis.
      for x in c.execute("select * from v211_split_members"):
        tid=topic_by_source[("split_v211",x["proposal_id"])]
        c.execute("insert or ignore into v22_company_topic_links values (?,?,?,?,?,?,?)",(company_by_profile[x["profile_id"]],tid,"primary_candidate",x["product_basis"],x["technology_basis"],"V2.1.1拆分依据","pending"))
      # Select a primary classification only when product and technology are both specific.
      for p in profiles:
        cid=company_by_profile[p["profile_id"]]
        link=c.execute("""select l.*,t.field_id,f.industry_id from v22_company_topic_links l join v22_topics t using(topic_id) join v22_fields f using(field_id) where l.company_id=? and l.product_basis<>'待补充' and l.technology_basis<>'待补充' order by case l.link_role when 'primary_candidate' then 0 else 1 end""",(cid,)).fetchone()
        if link:c.execute("update v22_company_profiles set primary_industry_id=?,primary_field_id=?,primary_topic_id=?,classification_status='classified_proposed',classification_reason='产品和技术字段均有现有材料支持' where company_id=?",(link["industry_id"],link["field_id"],link["topic_id"],cid))
        for tag in json.loads(c.execute("select keywords_json from v2_company_profiles where profile_id=?",(p["profile_id"],)).fetchone()[0] or "[]"):
          c.execute("insert or ignore into v22_company_tags values (?,?,?,?)",(cid,tag,"V2.0技术关键词迁移，待人工确认","pending"))
      # Events are unique independently of topic links.
      all_event_rows=[]
      for (kind,ref),tid in topic_by_source.items():
        if kind=="retained_v2":all_event_rows += [(tid,dict(r)) for r in c.execute("select * from v2_event_topic_links where topic_id=?",(ref,))]
        else:
          names=[r[0] for r in c.execute("select p.company_name from v211_split_members m join v2_company_profiles p using(profile_id) where m.proposal_id=?",(ref,))]
          source=c.execute("select source_topic_id from v211_split_proposals where proposal_id=?",(ref,)).fetchone()[0]
          if names:all_event_rows += [(tid,dict(r)) for r in c.execute("select * from v2_event_topic_links where topic_id=? and company_name in (%s)"%",".join("?"*len(names)),(source,*names))]
      for tid,e in all_event_rows:
        eid=uid("event:"+e["event_source_type"]+":"+e["event_ref"]);c.execute("insert or ignore into v22_events values (?,?,?,?,?,?,?,?)",(eid,e["event_source_type"],e["event_ref"],e["company_name"],e["round_original"],e["amount_original"],e["disclosure_date"],e["event_source_type"]))
        c.execute("insert or ignore into v22_event_topics values (?,?)",(eid,tid))
        match=c.execute("select company_id from v22_companies where display_name=? limit 1",(e["company_name"],)).fetchone()
        if match:c.execute("insert or ignore into v22_event_companies values (?,?,?)",(eid,match[0],"financing_company"))
    print(json.dumps({"industries":c.execute('select count(*) from v22_industries').fetchone()[0],"fields":c.execute('select count(*) from v22_fields').fetchone()[0],"source_topics":len(sources),"duplicate_pairs":c.execute("select count(*) from v22_topic_relations").fetchone()[0],"companies":len(profiles)},ensure_ascii=False));c.close()
if __name__=="__main__":main()
