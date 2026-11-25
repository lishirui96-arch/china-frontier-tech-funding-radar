from __future__ import annotations
import json,sqlite3,uuid,re
from datetime import datetime,timezone
from funding_radar.db import database_path
from funding_radar.migrations import migrate
NS=uuid.UUID("d9b4a8b2-728e-44bc-a106-43f965c55143")
def uid(x):return str(uuid.uuid5(NS,x))
def now():return datetime.now(timezone.utc).isoformat()
GENERIC_PRODUCTS={"机器人产品与系统","计算芯片及相关系统","生命科学产品或研发平台","AI软件、平台或解决方案","量子计算或传感产品"}
GENERIC_TECH={"感知、决策、控制及机电系统集成","芯片架构、能效优化与高速互连","生物实验、药物研发与临床转化","模型、数据与行业知识工程","量子器件、操控、软件或精密测量"}
CONCLUSIONS={
"机器人视触觉与精密感知":("C","调整企业成员后提交确认","优理奇有视触觉产品与技术依据；纬钛机器人的现有字段仍为机器人通用描述，需补充具体传感产品后再纳入"),
"工业与室外场景自主作业机器人":("E","暂缓","多家企业只有场景宣传和机器人通用描述，尚不能证明共享同一自主作业技术栈"),
"通用人形与服务具身系统":("C","调整企业成员后提交确认","存在优理奇重复实体，且至简动力等成员缺少具体产品技术字段；先完成实体映射和成员证据补充"),
"端侧推理芯片与系统集成":("E","暂缓","成员被共同赋予通用芯片描述，但端侧推理、交换芯片、CPU与SoC架构并非同一技术问题"),
"AI算力集群的光互连与硅光交换":("C","调整企业成员后提交确认","启明光子有具体光频梳/CPO依据，其余成员需补充硅光、OCS或高速光互连的具体产品技术"),
"虚拟细胞与生物基础模型":("C","调整企业成员后提交确认","无界进化有具体虚拟细胞产品栈；元示科技仍需补充模型、实验闭环和产品形态依据"),
"AI药物与RNA结构设计":("E","暂缓","AI药物设计工具与RNA结构/核酸药物平台存在上下游关系，但当前通用生物技术字段不足以证明共同技术"),
"核酸药物与RNA技术平台":("E","暂缓","企业业务指向核酸药物，但递送、靶点、RNA结构或药物形式等核心技术依据不足"),
"ADC与抗体偶联药物":("E","暂缓","融资正文支持ADC方向，但载荷、连接子、抗体与耐药机制等共同技术尚未结构化核实"),
"细胞工程与精准细胞治疗":("E","暂缓","体内细胞工程与细胞治疗产品可能存在不同技术路线，现有字段过于宽泛"),
"质谱与高端分析仪器":("C","调整企业成员后提交确认","瑞莱谱具有临床质谱依据；伯仪现有字段更接近蛋白研究/AI解决方案，需核实是否属于质谱仪器"),
"临床检测与生命科学仪器":("E","暂缓","两家企业主营业务和具体仪器均未明确，无法建立共同技术边界"),
"多路线量子计算硬件与系统工程":("D","建议拆分","中性原子、原子光子、超导或其他硬件路线的器件、操控和系统工程差异显著，泛化量子描述不足以支撑单一主题"),
"量子计算软件栈与AI混合计算":("E","暂缓","需要分别证明量子编译、算法映射和经典-量子混合计算产品，当前字段仍为方向性描述")}
def grade(member):
    business=member["primary_business"] not in ("","待补充")
    product=member["product_basis"] not in GENERIC_PRODUCTS and member["product_basis"] not in ("","待补充")
    tech=member["technology_basis"] not in GENERIC_TECH and member["technology_basis"] not in ("","待补充")
    evidence=bool(json.loads(member["evidence_urls_json"] or "[]"))
    if product and tech and evidence:return "A"
    if product and not tech:return "B"
    if tech and not product:return "C"
    return "D"
def main():
    migrate();c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row;ts=now()
    with c:
      for table in ("v231_cross_topic_reviews","v231_entity_reviews","v231_member_quality","v231_topic_admission_reviews"):c.execute(f"delete from {table}")
      target=[dict(r) for r in c.execute("""select t.* from v23_review_cards r join v22_topics t on t.topic_id=r.source_topic_id where r.recommendation='建议确认正式主题'""")]
      for t in target:
        code,label,reason=CONCLUSIONS[t["candidate_name"]]
        members=[dict(r) for r in c.execute("""select c.company_id,c.display_name,p.primary_business,p.evidence_urls_json,l.product_basis,l.technology_basis,l.evidence_basis from v22_company_topic_links l join v22_companies c using(company_id) join v22_company_profiles p using(company_id) where l.topic_id=?""",(t["topic_id"],))]
        events=[dict(r) for r in c.execute("select e.* from v22_event_topics x join v22_events e using(event_id) where x.topic_id=?",(t["topic_id"],))]
        grades=[]
        for m in members:
          g=grade(m);grades.append(g);business="明确" if m["primary_business"] not in ("","待补充") else "缺失"
          product="具体" if m["product_basis"] not in GENERIC_PRODUCTS and m["product_basis"]!="待补充" else "泛化或缺失"
          tech="具体" if m["technology_basis"] not in GENERIC_TECH and m["technology_basis"]!="待补充" else "泛化或缺失"
          evidence="有可追溯URL" if json.loads(m["evidence_urls_json"] or "[]") else "现有结构化画像无URL"
          promo="较高" if re.search(r"加速|推动|布局|落地|升级|规模化",m["primary_business"] or "") else "一般"
          c.execute("insert into v231_member_quality values (?,?,?,?,?,?,?,?,?)",(t["topic_id"],m["company_id"],g,business,product,tech,evidence,promo,"需补充后纳入" if g!="A" else "可支持主题准入"))
        status_count={s:sum(e["data_status"]==s for e in events) for s in ("formal","A_candidate","B_candidate")}
        common=t["technical_boundary"]
        differences="成员产品形态、技术路线与应用场景需逐家对照；不能用共同产业标签替代共同技术"
        boundary="主题边界需限定到可验证产品和技术问题；上下游关系仅作为交叉标签"
        cross="允许企业跨主题，但每条关系必须保留独立产品或技术依据"
        duplicate="优理奇实体重复影响企业与事件计数" if t["candidate_name"]=="通用人形与服务具身系统" else "未发现已登记实体重复直接影响"
        c.execute("insert into v231_topic_admission_reviews values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(uid("review:"+t["topic_id"]),t["topic_id"],code+". "+label,reason,common,"A/B/C/D成员分级显示当前证据强弱",differences,boundary,cross,len({m['company_id'] for m in members}),len({e['event_id'] for e in events}),status_count["formal"],status_count["A_candidate"],status_count["B_candidate"],duplicate,ts))
      # Duplicate entity: preserve IDs and recommend merge only after human confirmation.
      dup=c.execute("""select d.*,l.company_id left_company_id,r.company_id right_company_id,l.display_name left_name,r.display_name right_name
        from v211_entity_duplicate_checks d join v22_companies l on l.source_profile_id=d.left_profile_id join v22_companies r on r.source_profile_id=d.right_profile_id
        where (l.display_name like '优理奇%' and r.display_name like '优理奇%')""").fetchone()
      if dup:
        left_events=[dict(r) for r in c.execute("select e.* from v22_event_companies x join v22_events e using(event_id) where x.company_id=?",(dup["left_company_id"],))];right_events=[dict(r) for r in c.execute("select e.* from v22_event_companies x join v22_events e using(event_id) where x.company_id=?",(dup["right_company_id"],))]
        mapping=json.dumps({"left_company_id":dup["left_company_id"],"right_company_id":dup["right_company_id"],"preserve_both_until_confirmed":True},ensure_ascii=False)
        c.execute("insert into v231_entity_reviews values (?,?,?,?,?,?,?,?,?,?,?)",(uid("entity:unix"),dup["left_company_id"],dup["right_company_id"],"品牌名和法定主体线索高度一致，但一条名称括号截断","现有资料未提供可靠统一社会信用代码","业务均指向优理奇/UniX AI具身机器人","一侧有Wanda/Panther具体产品，另一侧仅为媒体泛化描述",json.dumps({"left":left_events,"right":right_events},ensure_ascii=False),"建议人工确认同一主体后建立主从ID映射，不自动合并",mapping,"pending"))
      # Preserve cross-topic relations for the 14-topic scope.
      target_ids={t["topic_id"] for t in target}
      for r in c.execute("""select l.* from v22_company_topic_links l where l.topic_id in (select source_topic_id from v23_review_cards where recommendation='建议确认正式主题') and l.company_id in (select company_id from v22_company_topic_links group by company_id having count(*)>1)"""):
        rec="保留并补充产品级依据" if r["product_basis"]!="待补充" and r["technology_basis"]!="待补充" else "暂缓该交叉关系"
        c.execute("insert into v231_cross_topic_reviews values (?,?,?,?,?,?)",(r["company_id"],r["topic_id"],"合理交叉需由不同产品或技术能力支持",r["product_basis"],r["technology_basis"],rec))
    print(json.dumps({"topics":c.execute('select count(*) from v231_topic_admission_reviews').fetchone()[0],"members":c.execute('select count(*) from v231_member_quality').fetchone()[0],"grades":{r['quality_grade']:r['n'] for r in c.execute('select quality_grade,count(*) n from v231_member_quality group by quality_grade')},"conclusions":{r['admission_conclusion']:r['n'] for r in c.execute('select admission_conclusion,count(*) n from v231_topic_admission_reviews group by admission_conclusion')}},ensure_ascii=False));c.close()
if __name__=="__main__":main()
