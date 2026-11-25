from __future__ import annotations
import json,re,sqlite3,uuid
from collections import Counter
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate

NS=uuid.UUID("957d27c1-0f71-48f8-ae34-602c108f6cc7")
def uid(x): return str(uuid.uuid5(NS,x))
def now(): return datetime.now(timezone.utc).isoformat()
CONTAM=re.compile(r"领投|投资|融资|天使\+?轮|Pre-A|A轮|B轮|亿元|万元|资本|国投|创投|加码|完成.*轮|独家")
GENERIC={"机器人产品与系统","感知、决策、控制及机电系统集成","AI软件、平台或解决方案","模型、数据与行业知识工程","生命科学产品或研发平台","生物实验、药物研发与临床转化","电池材料或制造装备","材料界面、工艺放大与制造一致性","量子计算或传感产品","量子器件、操控、软件或精密测量"}

def clean(value):
    value=(value or "").strip()
    return "待补充" if not value or value=="待补充" or CONTAM.search(value) else value
def norm(name):
    return re.sub(r"（.*?[）)]|\(.*?\)|有限责任公司|股份有限公司|有限公司|机器人|智能科技|科技|[\s·]","",name).lower()
def split_group(topic,company,text):
    if topic=="室外与工业具身机器人的自主作业系统": return "通用人形与服务具身系统" if re.search(r"优理奇|至简动力|九天创智|Wanda|Panther|人形",company+text) else "工业与室外场景自主作业机器人"
    if topic=="端侧AI芯片的能效与系统集成": return "存算一体与存储架构" if re.search(r"后摩|存算|存内",company+text) else "端侧推理芯片与系统集成"
    if topic=="高性能功能材料的国产化与工程验证":
        if re.search(r"电解质|蓝固",company+text): return "固态电池电解质材料"
        if re.search(r"磁材|辰达",company+text): return "高性能磁性材料"
        if re.search(r"涂料|防污|盖科",company+text): return "特种防护与功能涂层"
        return "其他功能材料观察项"
    if topic=="固态电池关键材料与规模化装备": return "固态电池量产装备" if "高能数造" in company else "固态电池关键材料"
    if topic=="商业航天测运控与低成本任务保障":
        if re.search(r"测控|地面|天链",company+text): return "商业航天测运控与地面服务"
        if re.search(r"遥感|卫星|谱星|丝路天图",company+text): return "卫星载荷与遥感数据服务"
        return "深空动力与任务系统观察项"
    if topic=="虚拟细胞与AI药物设计的实验闭环": return "虚拟细胞与生物基础模型" if re.search(r"元示|虚拟细胞",company+text) else "AI药物与RNA结构设计"
    if topic=="核酸、ADC与新型生物药载荷平台":
        if re.search(r"RNA|核酸|砺博|昂拓",company+text): return "核酸药物与RNA技术平台"
        if re.search(r"ADC|抗体",company+text): return "ADC与抗体偶联药物"
        return "其他新型生物药载荷观察项"
    if topic=="生命科学检测与高端分析仪器": return "质谱与高端分析仪器" if re.search(r"质谱|伯仪|瑞莱谱",company+text) else "临床检测与生命科学仪器"
    return None

def main():
    migrate();c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row;ts=now()
    with c:
      for table in ("v211_split_members","v211_split_proposals","v211_shared_company_reviews","v211_product_technology_topic_links","v211_entity_duplicate_checks","v211_profile_reviews"): c.execute(f"delete from {table}")
      profiles=[dict(r) for r in c.execute("""select p.*,i.name industry_name,f.name field_name from v2_company_profiles p join v2_industry_directions i using(industry_id) join v2_technology_fields f using(field_id)""")]
      for p in profiles:
        sb,sp,st,ss,sc=map(clean,(p["primary_business"],p["core_products"],p["core_technologies"],p["application_scenarios"],p["value_chain_position"]))
        issues=[]
        for key,label in (("primary_business","主营业务"),("core_products","核心产品"),("core_technologies","核心技术")):
            value=p[key]
            if CONTAM.search(value or ""): issues.append(label+"混入融资或投资信息")
            if value in GENERIC: issues.append(label+"为规则生成的泛化描述")
            if value in ("","待补充"): issues.append(label+"缺失")
        if any(x in GENERIC for x in (sp,st)): sp="待补充" if sp in GENERIC else sp;st="待补充" if st in GENERIC else st
        missing=sum(x=="待补充" for x in (sb,sp,st)); quality="accurate" if not issues and p["profile_status"]=="evidence_supported" else ("missing_core_business" if missing>=2 else "needs_revision")
        reason="现有字段有具体产品和技术依据" if quality=="accurate" else "融资信息与企业业务严格分离；缺乏依据的字段建议改为待补充"
        c.execute("insert into v211_profile_reviews values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(uid("review:"+p["profile_id"]),p["profile_id"],quality,p["company_name"],p["company_name"],p["primary_business"],sb,p["core_products"],sp,p["core_technologies"],st,p["application_scenarios"],ss,p["value_chain_position"],sc,p["industry_name"],p["industry_name"],p["field_name"],p["field_name"],json.dumps(issues,ensure_ascii=False),reason,p["evidence_urls_json"],"pending",ts))
      for i,left in enumerate(profiles):
        for right in profiles[i+1:]:
          nl,nr=norm(left["company_name"]),norm(right["company_name"])
          if nl and nr and (nl==nr or (min(len(nl),len(nr))>=3 and (nl in nr or nr in nl))):
            rel="probable_same_entity" if nl==nr else "needs_manual_review"
            c.execute("insert or ignore into v211_entity_duplicate_checks values (?,?,?,?,?,?)",(uid("dup:"+left["profile_id"]+right["profile_id"]),left["profile_id"],right["profile_id"],rel,"标准化名称相同或存在包含关系","pending"))
      links=[dict(r) for r in c.execute("""select l.*,p.company_name,p.core_products,p.core_technologies,p.evidence_urls_json,t.candidate_name from v2_company_topic_links l join v2_company_profiles p using(profile_id) join v2_candidate_topics t using(topic_id) where l.is_current=1""")]
      for x in links:
        product=clean(x["core_products"]);tech=clean(x["core_technologies"]);fit="supported" if product!="待补充" and tech!="待补充" else "insufficient_evidence"
        if x["company_name"].startswith("启明光子") and "基础设施" in x["candidate_name"]: fit="likely_keyword_misclassification"
        if x["company_name"]=="蓝固新能源" and "高性能功能材料" in x["candidate_name"]: fit="secondary_cross_tag"
        c.execute("insert into v211_product_technology_topic_links values (?,?,?,?,?,?,?,?)",(uid("link:"+x["topic_id"]+x["profile_id"]),x["profile_id"],x["topic_id"],product,tech,fit,x["evidence_urls_json"],"pending"))
      shared=[dict(r) for r in c.execute("""select p.profile_id,p.company_name,count(*) n from v2_company_topic_links l join v2_company_profiles p using(profile_id) where l.is_current=1 group by p.profile_id having count(*)>1""")]
      for p in shared:
        bases=[dict(r) for r in c.execute("""select t.candidate_name,x.product_basis,x.technology_basis,x.topic_fit from v211_product_technology_topic_links x join v2_candidate_topics t using(topic_id) where x.profile_id=?""",(p["profile_id"],))]
        conclusions={"优理奇":"合理多产品/多技术交叉","启明光子（北京）科技有限公司":"光互连主题合理，AI云基础设施关联建议移除","蓝固新能源":"固态电解质为主，泛材料主题仅作次级标签","砺博生物":"AI RNA设计与核酸药物管线形成合理上下游交叉"}
        conclusion=conclusions.get(p["company_name"],"需按产品与技术依据人工复核")
        c.execute("insert into v211_shared_company_reviews values (?,?,?,?,?,?)",(p["profile_id"],p["n"],conclusion,json.dumps(bases,ensure_ascii=False),"不以融资新闻关键词作为多主题依据","pending"))
      split_topics=[dict(r) for r in c.execute("""select t.* from v2_candidate_topics t join v21_topic_audits a using(topic_id) where a.recommendation='拆分'""")]
      for topic in split_topics:
        members=[dict(r) for r in c.execute("""select p.* from v2_company_topic_links l join v2_company_profiles p using(profile_id) where l.topic_id=? and l.is_current=1""",(topic["topic_id"],))]
        groups={}
        for p in members:
          text=" ".join(str(p[k] or "") for k in ("primary_business","core_products","core_technologies"));group=split_group(topic["candidate_name"],p["company_name"],text) or "待人工分组";groups.setdefault(group,[]).append(p)
        for group,items in groups.items():
          refs=[r["event_ref"] for r in c.execute("select distinct event_ref from v2_event_topic_links where topic_id=? and company_name in (%s)"%",".join("?"*len(items)),(topic["topic_id"],*[p["company_name"] for p in items]))]
          status=Counter(r["event_source_type"] for r in c.execute("select event_source_type from v2_event_topic_links where topic_id=? and company_name in (%s)"%",".join("?"*len(items)),(topic["topic_id"],*[p["company_name"] for p in items])))
          pid=uid("split:"+topic["topic_id"]+group);qual=len(items)>=2 and "其他" not in group and "待人工" not in group
          proposal_status="multi_company_candidate" if qual else ("needs_manual_split" if len(items)>=2 else "single_company_observation")
          c.execute("insert into v211_split_proposals values (?,?,?,?,?,?,?,?,?,?,?,?)",(pid,topic["topic_id"],group,"按产品形态、核心技术和产业链环节拆分",len(items),len(set(refs)),status["formal"],status["A_candidate"],status["B_candidate"],qual,proposal_status,"pending"))
          for p in items: c.execute("insert into v211_split_members values (?,?,?,?)",(pid,p["profile_id"],clean(p["core_products"]),clean(p["core_technologies"])))
    print(json.dumps({"profiles":len(profiles),"duplicates":c.execute('select count(*) from v211_entity_duplicate_checks').fetchone()[0],"shared":len(shared),"split_groups":c.execute('select count(*) from v211_split_proposals').fetchone()[0]},ensure_ascii=False));c.close()
if __name__=="__main__": main()
