from __future__ import annotations
import json,re,sqlite3,uuid
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate

NS=uuid.UUID("580ad33f-0874-4427-9670-83b426cb60fa")
def uid(s):return str(uuid.uuid5(NS,s))
def now():return datetime.now(timezone.utc).isoformat()
INDUSTRIES=[("robotics","机器人与具身智能"),("ai-compute","AI芯片与先进计算"),("advanced-manufacturing","高端装备与先进制造"),("energy-materials","新能源与新材料"),("aerospace","商业航天与低空经济"),("life-science","生物制造与生命科学"),("quantum","量子科技"),("other","其他新兴技术")]
FIELDS={
"robotics":["机器人本体与具身模型","关节执行与精密传动","机器人感知与触觉","脑机接口"],
"ai-compute":["AI推理与端侧芯片","光互连与光计算","AI计算基础设施","企业智能体与工业AI"],
"advanced-manufacturing":["增材制造与工业材料","智能制造装备","精密仪器与检测"],
"energy-materials":["固态电池材料与装备","高性能功能材料","能源装备"],
"aerospace":["卫星制造与遥感载荷","航天测运控与动力","无人机与低空交通"],
"life-science":["AI生物模型与药物研发","细胞与基因技术","核酸与抗体药物","生物检测与临床分析"],
"quantum":["量子计算硬件","量子软件与混合计算","量子传感"],"other":["数字健康与消费科技","待补充技术方向"]}
TOPICS=[
("outdoor-embodied","室外与工业具身机器人的自主作业系统","robotics","机器人本体与具身模型",r"九天创智|富唯智能|擎天智能|智蜂创元|至简动力|优理奇|简智机器人|飒智智能", "面向非结构化室外或工业现场的感知、决策、导航与作业闭环"),
("robot-joints","机器人关节执行与高密度机电集成","robotics","关节执行与精密传动",r"华盛技术|关节|减速器|力矩电机", "关节模组、精密传动、伺服驱动和热/功率密度工程"),
("robot-sensing","机器人视触觉与精密感知","robotics","机器人感知与触觉",r"纬钛机器人|触觉|电子皮肤", "机器人接触感知、视触觉融合和精密操作反馈"),
("bci","脑机接口的微创采集与神经功能重建","robotics","脑机接口",r"脑机|谱思科技|主动科技|元纽科技|臻泰智能|Rex Bionics", "侵入式、微创或睡眠脑机接口及神经康复应用"),
("edge-ai-chip","端侧AI芯片的能效与系统集成","ai-compute","AI推理与端侧芯片",r"诚恒微|后摩智能|NovaSilicon|灵睿智芯|奕泰智能|通芯智能|凌川科技|泛函数", "在功耗、存储带宽和端侧实时性约束下实现AI计算"),
("optical-interconnect","AI算力集群的光互连与硅光交换","ai-compute","光互连与光计算",r"英伟芯|孛璞半导体|华毅瀛飞|智子光垣|光互连|硅光|光计算", "高速光互连、硅光器件、光交换与光计算芯片"),
("ai-infra","专属AI云与智能体基础设施","ai-compute","AI计算基础设施",r"中国电子云|以太之心|柏川数据|利普思|曦选创智|AI数据中心|算力", "算力、模型、数据和智能体运行基础设施"),
("agent-industrial-ai","企业智能体与工业知识闭环","ai-compute","企业智能体与工业AI",r"知业科技|星尘浩宇|观测云|ARTi|造物潭|青葵智造|天云创鸿|企业级AI|工业AI", "企业流程、工业知识和智能体的可交付、可治理应用"),
("continual-learning","大模型持续学习与实时自进化","ai-compute","企业智能体与工业AI",r"无涯智远|持续学习|自进化", "模型部署后的参数更新、经验内化和灾难性遗忘缓解"),
("additive-materials","高性能材料与增材制造量产体系","advanced-manufacturing","增材制造与工业材料",r"博理科技|3D打印|PEKK|湃沃斯", "材料配方、成型装备和批量一致性交付"),
("solid-battery","固态电池关键材料与规模化装备","energy-materials","固态电池材料与装备",r"蓝固新能源|高能数造|固态电池|固态电解质", "固态电解质界面稳定性、材料制备与量产装备"),
("functional-materials","高性能功能材料的国产化与工程验证","energy-materials","高性能功能材料",r"国科炭美|盖科材料|辰达新材|磁材|防污涂料|材料", "关键材料性能、工艺放大、认证和长期工况验证"),
("space-remote","卫星载荷与定量遥感数据链","aerospace","卫星制造与遥感载荷",r"谱星航天|遥感|卫星", "卫星载荷、光谱定量遥感与数据应用"),
("space-control","商业航天测运控与低成本任务保障","aerospace","航天测运控与动力",r"天链测控|北辰航天|瑞启深空|航天", "测运控、地面系统、深空与商业航天任务保障"),
("low-altitude","长航时无人机与低空运力服务","aerospace","无人机与低空交通",r"排云智航|零界航空|eVTOL|无人机", "长航时飞行器、eVTOL交易和低空运力运营"),
("ai-cell-drug","虚拟细胞与AI药物设计的实验闭环","life-science","AI生物模型与药物研发",r"元示科技|途深智合|砺博生物|虚拟细胞|AI药物", "模型预测、自动实验、数据反馈和药物设计闭环"),
("cell-therapy","细胞工程与精准细胞治疗","life-science","细胞与基因技术",r"三有利康|阿法纳生物|细胞治疗|细胞工程", "细胞亚群、体内工程、工艺一致性和临床转化"),
("novel-biologics","核酸、ADC与新型生物药载荷平台","life-science","核酸与抗体药物",r"昂拓生物|拓济医药|金领生物|湃来生物|核酸|ADC|抗体", "核酸调控、抗体偶联、抗毒力素等差异化药物平台"),
("bio-analysis","生命科学检测与高端分析仪器","life-science","生物检测与临床分析",r"瑞莱谱医疗|伯仪集团|质谱|蛋白质研究|英捷信医疗|景芮医疗", "质谱、蛋白分析和临床检测设备的国产化交付"),
("neutral-atom-quantum","中性原子与原子光子量子计算硬件","quantum","量子计算硬件",r"原子矩阵|原基量子|国测量子|幺正量子", "量子比特操控、原子/光子芯片和量子计算系统工程"),
("quantum-software","量子计算软件栈与AI混合计算","quantum","量子软件与混合计算",r"酉术量子|洽道量子|量子.*翻译|混合计算", "量子编译、算法映射和经典-量子混合计算"),
("quantum-sensing","量子精密传感的工程化应用","quantum","量子传感",r"原磁智造|量子磁场", "量子磁场传感器、仪器化和产业场景验证")]

def classify_all(text):
    return [topic for topic in TOPICS if re.search(topic[4], text, re.I)]
def detail(text):
    rules=[(r"脑机","脑机接口系统","柔性电极、神经信号采集与解码"),(r"质谱","临床质谱仪器与检测系统","质谱分析、精密检测与试剂协同"),(r"芯片|SoC|RISC-V","计算芯片及相关系统","芯片架构、能效优化与高速互连"),(r"机器人|具身","机器人产品与系统","感知、决策、控制及机电系统集成"),(r"电池|电解质","电池材料或制造装备","材料界面、工艺放大与制造一致性"),(r"细胞|药物|生物|医疗","生命科学产品或研发平台","生物实验、药物研发与临床转化"),(r"量子","量子计算或传感产品","量子器件、操控、软件或精密测量"),(r"AI|智能","AI软件、平台或解决方案","模型、数据与行业知识工程")]
    for pat,prod,tech in rules:
        if re.search(pat,text,re.I):return prod,tech
    return "待补充","待补充"

def main():
    migrate();db=sqlite3.connect(database_path());db.row_factory=sqlite3.Row;ts=now()
    with db:
        for t in ("v2_event_topic_links","v2_company_topic_links","v2_candidate_topics","v2_company_profiles","v2_technology_fields","v2_industry_directions"):
            db.execute(f"delete from {t}")
        for i,(iid,name) in enumerate(INDUSTRIES,1):db.execute("insert into v2_industry_directions values (?,?,?,?)",(iid,name,"V2.0技术主题导航入口",i))
        field_ids={}
        for iid,names in FIELDS.items():
            for name in names:
                fid=uid("field:"+iid+":"+name);field_ids[(iid,name)]=fid;db.execute("insert into v2_technology_fields values (?,?,?,?)",(fid,iid,name,"按产品、核心技术和工程问题形成的技术领域"))
        topics={}
        for tid,name,iid,field,pat,boundary in TOPICS:
            topics[tid]=uid("topic:"+tid);db.execute("insert into v2_candidate_topics values (?,?,?,?,?,?,?,?,?,'pending',NULL,0,?,?)",(topics[tid],name,iid,field_ids[(iid,field)],f"候选主题：{boundary}",boundary,"至少一条现有融资材料明确涉及该产品或技术问题","需要用户确认主题边界、名称及企业成员", "multi_company",ts,ts))
        events=[dict(x) for x in db.execute("""select u.event_unit_id ref,u.sample_eligibility_status status,u.company_id entity_id,a.normalized_company_name name,a.source_title title,a.source_url url,
          a.normalized_primary_category primary_cat,a.normalized_secondary_track secondary,u.adjudicated_round round_name,u.amount_original,u.disclosure_date,e.primary_business,e.core_products,e.evidence_urls_json
          from v14_event_units u join v13_candidate_quality_audits a using(audit_id) join v13_company_entities e using(company_id)
          where u.sample_eligibility_status in ('A_statistical','B_pending')""")]
        profiles={}
        for ev in events:
            text=" ".join(str(ev.get(k) or "") for k in ("name","title","primary_business","core_products","secondary")); hits=classify_all(text); hit=hits[0] if hits else None
            if hit:tid,tname,iid,field,pattern,boundary=hit
            else: tid=None;iid="other";field="待补充技术方向"
            prod,tech=detail(text); business=ev["primary_business"] if ev["primary_business"] not in ("待核实","") else re.sub(r"^.*?融资[，,]?","",ev["title"])[:160] or "待补充"
            key="candidate:"+ev["entity_id"]
            if key not in profiles:
                pid=uid("profile:"+key);profiles[key]=pid;status="pending_supplement" if prod=="待补充" else "partially_supported"
                db.execute("insert into v2_company_profiles values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,key,ev["name"],"candidate_entity",ev["entity_id"],business,prod,tech,"依据现有正文待进一步细化",boundary if hit else "待补充",iid,field_ids[(iid,field)],json.dumps(sorted(set(re.findall(r"AI|SoC|RISC-V|脑机|质谱|量子|机器人|具身|芯片|电池|细胞|药物|遥感|光互连",text))),ensure_ascii=False),ev["evidence_urls_json"],status,ts,ts))
            for tid,tname,topic_iid,topic_field,pattern,boundary in hits:
                pid=profiles[key];db.execute("insert or ignore into v2_company_topic_links values (?,?,?,?,?)",(topics[tid],pid,f"产品或技术材料命中主题边界：{boundary}",1,ts));stype="A_candidate" if ev["status"]=="A_statistical" else "B_candidate";db.execute("insert or ignore into v2_event_topic_links values (?,?,?,?,?,?,?)",(topics[tid],stype,ev["ref"],ev["name"],ev["round_name"],ev["amount_original"],ev["disclosure_date"]))
        # Existing formal profiles remain separate and retain their approved event links.
        for p in db.execute("""select p.*,c.official_name,e.event_id,e.round_original,e.amount_original,e.announcement_date,ic.name industry_name
          from company_technology_profiles p join companies c using(company_id) left join funding_events e using(company_id)
          join industry_categories ic on ic.category_id=p.primary_category_id"""):
            text=" ".join(str(p[k] or "") for k in ("official_name","primary_business","core_products","core_technologies","secondary_track"));hits=classify_all(text);hit=hits[0] if hits else None
            iid=hit[2] if hit else "other";field=hit[3] if hit else "待补充技术方向";key="formal:"+p["company_id"]
            if key not in profiles:
                pid=uid("profile:"+key);profiles[key]=pid;db.execute("insert into v2_company_profiles values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,key,p["official_name"],"formal_company",p["company_id"],p["primary_business"],p["core_products"],p["core_technologies"],p["application_scenarios"],p["value_chain_position"],iid,field_ids[(iid,field)],p["cross_domain_tags"] or "[]","[]","evidence_supported",ts,ts))
            if p["event_id"]:
                for tid,tname,topic_iid,topic_field,pattern,boundary in hits:
                    db.execute("insert or ignore into v2_company_topic_links values (?,?,?,?,?)",(topics[tid],profiles[key],"已有正式企业技术画像与主题技术边界匹配",1,ts));db.execute("insert or ignore into v2_event_topic_links values (?,?,?,?,?,?,?)",(topics[tid],"formal",p["event_id"],p["official_name"],p["round_original"],p["amount_original"],p["announcement_date"]))
        # Convert themes with one company into observation items; remove empty themes.
        for row in db.execute("select topic_id,count(*) n from v2_company_topic_links group by topic_id").fetchall():
            db.execute("update v2_candidate_topics set topic_kind=? where topic_id=?",("single_company_observation" if row["n"]==1 else "multi_company",row["topic_id"]))
        db.execute("delete from v2_candidate_topics where topic_id not in (select topic_id from v2_company_topic_links)")
    print(json.dumps({"profiles":db.execute("select count(*) from v2_company_profiles").fetchone()[0],"industries":db.execute("select count(*) from v2_industry_directions").fetchone()[0],"fields":db.execute("select count(*) from v2_technology_fields").fetchone()[0],"topics":db.execute("select count(*) from v2_candidate_topics").fetchone()[0],"single":db.execute("select count(*) from v2_candidate_topics where topic_kind='single_company_observation'").fetchone()[0],"unclassified":db.execute("select count(*) from v2_company_profiles where industry_id='other'").fetchone()[0]},ensure_ascii=False));db.close()
if __name__=="__main__":main()
