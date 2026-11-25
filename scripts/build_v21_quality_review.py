from __future__ import annotations
import json,re,sqlite3,uuid
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate

NS=uuid.UUID("fc0b45dd-2ac0-4f50-86f2-280179f259bf")
def uid(x): return str(uuid.uuid5(NS,x))
def now(): return datetime.now(timezone.utc).isoformat()

SUGGESTIONS={
"室外与工业具身机器人的自主作业系统":("拆分","具身机器人的场景自主作业与系统集成","机器人与具身智能","机器人本体与具身模型","企业覆盖室外、工业和通用具身场景，产品形态与作业边界差异较大，应按场景和本体能力复核成员。"),
"脑机接口的微创采集与神经功能重建":("调整产业归属","脑机接口的神经信号采集与功能重建","脑科学与神经技术","脑机接口与神经工程","技术共同点明确，但脑机接口不宜长期挂在机器人产业下。"),
"机器人视触觉与精密感知":("保留",None,None,None,"围绕机器人接触感知、视觉融合和操作反馈，边界相对独立。"),
"机器人关节执行与高密度机电集成":("保留",None,None,None,"关节模组、传动、驱动和热管理形成明确的核心部件问题。"),
"企业智能体与工业知识闭环":("调整产业归属","企业智能体与工业知识闭环","AI软件与工业智能","企业智能体与工业AI","属于软件与行业智能，不应与芯片硬件共用一级产业。"),
"端侧AI芯片的能效与系统集成":("拆分",None,"AI芯片与先进计算",None,"成员可能同时包含端侧推理芯片、存算一体与通用处理器，需要按架构和使用场景拆分。"),
"专属AI云与智能体基础设施":("改名","AI算力与模型运行基础设施",None,None,"当前名称把专属云与智能体混在一起，建议突出算力、模型和数据运行底座。"),
"AI算力集群的光互连与硅光交换":("保留",None,None,None,"光芯片、硅光器件与光交换共同解决集群互连带宽和功耗问题。"),
"量子计算软件栈与AI混合计算":("调整产业归属",None,"量子科技","量子软件与混合计算","AI只是应用或协同计算方式，主题主体仍是量子软件栈。"),
"大模型持续学习与实时自进化":("单企业观察",None,"AI软件与工业智能","模型训练与持续学习","目前只有一家企业，暂不参与多企业主题排名。"),
"高性能功能材料的国产化与工程验证":("拆分",None,None,None,"材料类型、终端场景和产业链环节跨度过大，应拆分电子材料、磁性材料和防护涂层等子组。"),
"固态电池关键材料与规模化装备":("拆分",None,None,None,"材料与装备属于上下游关联但技术问题不同，建议保留关联同时分别形成材料和装备子主题。"),
"高性能材料与增材制造量产体系":("改名","增材制造材料、装备与批量交付",None,None,"主题应突出增材制造工艺链，而不是泛指高性能材料。"),
"商业航天测运控与低成本任务保障":("拆分",None,"商业航天","航天测运控与任务服务","航天动力、测运控与任务服务不宜只因航天标签合并。"),
"卫星载荷与定量遥感数据链":("保留",None,"商业航天","卫星制造、载荷与数据应用","载荷与定量遥感数据形成上下游闭环，但需排除仅泛称卫星的成员。"),
"长航时无人机与低空运力服务":("调整产业归属",None,"低空经济","无人机与低空交通","低空飞行器和运营服务应与商业航天分开导航。"),
"虚拟细胞与AI药物设计的实验闭环":("拆分",None,None,None,"虚拟细胞基础模型与AI药物设计虽共享实验反馈，但研究对象和产品交付不同。"),
"细胞工程与精准细胞治疗":("保留",None,None,None,"共同技术问题是细胞工程、工艺一致性与精准治疗转化。"),
"核酸、ADC与新型生物药载荷平台":("拆分",None,None,None,"核酸药物、ADC和其他载荷平台机制不同，不宜作为单一技术主题。"),
"生命科学检测与高端分析仪器":("拆分",None,None,None,"临床检测、质谱和科研仪器客户、验证路径和技术栈不同。"),
"中性原子与原子光子量子计算硬件":("改名","多路线量子计算硬件与系统工程",None,None,"成员可能包含中性原子、超导或光量子路线，当前名称过窄。"),
"量子精密传感的工程化应用":("单企业观察",None,None,None,"仅一家企业，技术价值可观察但不参与多企业排名。")}

TAXONOMY=[
("industry","机器人与具身智能","机器人与具身智能","retain","保留机器人本体、感知和核心执行部件；脑机接口另行提议。"),
("industry","AI芯片与先进计算","AI芯片与先进计算","retain","限定芯片、计算架构、互连和算力基础设施。"),
("industry","AI芯片与先进计算","AI软件与工业智能","add","承接企业智能体、工业AI和持续学习软件主题。"),
("industry","机器人与具身智能","脑科学与神经技术","add","承接脑机接口、神经信号采集和神经功能重建。"),
("industry","商业航天与低空经济","商业航天","split","航天器、卫星、测运控与发射任务独立导航。"),
("industry","商业航天与低空经济","低空经济","split","无人机、eVTOL和低空运营独立导航。"),
("field","高端装备与先进制造/智能制造装备","半导体装备与先进封装","add","现有其他方向中存在晶圆键合、TGV、PVD、刻蚀和检测设备集群。"),
("field","其他新兴技术/数字健康与消费科技","数字健康与医疗器械","rename","区分医疗器械、数字健康与一般消费科技。")]

def triage(text):
    rules=[
      (r"TGV|晶圆|PVD|刻蚀|EUV|半导体|EDA|掩模版","can_form_new_topic","高端装备与先进制造","半导体装备与先进封装","半导体装备与工艺支撑"),
      (r"无人机|扑翼|eVTOL|低空","existing_or_new","低空经济","无人机与低空交通","长航时无人机与低空运力服务"),
      (r"医疗|内镜|健康|慢病","can_form_new_topic","生物制造与生命科学","数字健康与医疗器械","数字健康与医疗器械"),
      (r"量子","existing_topic","量子科技","量子计算硬件","多路线量子计算硬件与系统工程"),
      (r"AI|模型|数据智能","single_observation_or_new","AI软件与工业智能","AI软件与行业应用","待人工判断AI应用边界"),
      (r"材料|涂料|磁材|化学品","existing_or_split","新能源与新材料","高性能功能材料","高性能功能材料的国产化与工程验证")]
    for pat,*result in rules:
        if re.search(pat,text,re.I): return result
    return ["unable_to_determine",None,None,None]

def main():
    migrate(); c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row;ts=now()
    with c:
      for table in ("v21_topic_overlaps","v21_topic_audits","v21_taxonomy_proposals","v21_profile_triage"): c.execute(f"delete from {table}")
      topics=[dict(r) for r in c.execute("select * from v2_candidate_topics")]
      members={t["topic_id"]:[dict(r) for r in c.execute("""select p.*,l.link_reason from v2_company_topic_links l join v2_company_profiles p using(profile_id) where l.topic_id=? and l.is_current=1""",(t["topic_id"],))] for t in topics}
      for t in topics:
        ms=members[t["topic_id"]]; weak=[m["company_name"] for m in ms if m["profile_status"]!="evidence_supported"]
        rec,new_name,new_ind,new_field,reason=SUGGESTIONS[t["candidate_name"]]
        issues=[]
        if weak: issues.append(f"{len(weak)}家企业画像证据仍不完整："+"、".join(weak))
        if len(ms)==1: issues.append("仅一家企业，不应参与多企业主题重要性排名")
        review=[{"company":m["company_name"],"business":m["primary_business"],"products":m["core_products"],"technologies":m["core_technologies"],"fit":"需复核" if m["profile_status"]!="evidence_supported" else "初步匹配"} for m in ms]
        c.execute("insert into v21_topic_audits values (?,?,?,?,?,?,?,?,?,?,?,?)",(uid("audit:"+t["topic_id"]),t["topic_id"],rec,new_name,new_ind,new_field,"成员围绕当前技术边界存在产品或工程问题关联","依据成员产品、技术和产业链位置评估；不以融资标题或AI标签单独归类",json.dumps(issues,ensure_ascii=False),reason,json.dumps(review,ensure_ascii=False),ts))
      for i,left in enumerate(topics):
        a={m["profile_id"] for m in members[left["topic_id"]]}
        for right in topics[i+1:]:
          b={m["profile_id"] for m in members[right["topic_id"]]}; shared=len(a&b); j=shared/len(a|b) if a|b else 0
          rel="shared_member" if shared else ("same_field" if left["field_id"]==right["field_id"] else "distinct")
          note="共享企业需检查多标签是否合理" if shared else ("同一技术领域但当前成员不重叠" if rel=="same_field" else "未发现企业层直接重叠")
          c.execute("insert into v21_topic_overlaps values (?,?,?,?,?,?)",(left["topic_id"],right["topic_id"],shared,j,rel,note))
      for i,(level,current,suggested,ptype,reason) in enumerate(TAXONOMY): c.execute("insert into v21_taxonomy_proposals values (?,?,?,?,?,?,?,?,?)",(uid(f"tax:{i}"),level,current,current.split("/")[-1],None,suggested,ptype,reason,"pending"))
      profiles=[dict(r) for r in c.execute("select * from v2_company_profiles where profile_status='pending_supplement' or industry_id='other'")]
      for p in profiles:
        text=" ".join(str(p[k] or "") for k in ("company_name","primary_business","core_products","core_technologies","application_scenarios","value_chain_position"));disp,ind,field,topic=triage(text)
        missing="、".join(k for k,label in (("primary_business","主营业务"),("core_products","核心产品"),("core_technologies","核心技术"),("application_scenarios","应用场景"),("value_chain_position","产业链位置")) if p[k] in ("待补充",""))
        evidence="待补充" if p["profile_status"]=="pending_supplement" else "现有画像可支持初步建议"
        c.execute("insert into v21_profile_triage values (?,?,?,?,?,?,?,?,?,?,?)",(p["profile_id"],p["profile_status"]=="pending_supplement",p["industry_id"]=="other",disp,ind,field,topic,evidence,missing or "无明显缺失",("仅提出建议；" if disp!="unable_to_determine" else "现有材料不足，")+"不修改V2.0画像" ,"pending"))
    print(json.dumps({"topics":len(topics),"overlap_pairs":len(topics)*(len(topics)-1)//2,"triage":len(profiles),"pending":sum(p['profile_status']=='pending_supplement' for p in profiles),"other":sum(p['industry_id']=='other' for p in profiles)},ensure_ascii=False));c.close()
if __name__=="__main__": main()
