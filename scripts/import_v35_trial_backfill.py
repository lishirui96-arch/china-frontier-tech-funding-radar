from __future__ import annotations

import hashlib
import json
import uuid

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


NAMESPACE = uuid.UUID("37e8cb20-23c8-5c30-b11f-7efe8ead74c0")
BATCH_ID = str(uuid.uuid5(NAMESPACE, "2026-10-27_2026-11-01_trial"))

INDUSTRIES = {
    "robot": "c0983de5-d08f-53b8-901c-d750f8e863c2",
    "compute": "c9a16792-5f10-51fb-9437-875c75b8a7f0",
    "energy": "d97f43a8-6431-53ab-8a0f-7b249293c6ec",
    "equipment": "596a5389-b98a-5194-80d4-6aab5261f7bc",
    "bio": "8ed1f51f-0901-5b42-bac7-06ce139ce2a9",
    "brain": "04bdd201-fbd8-5c25-a946-0630f8102dcf",
    "quantum": "d4dd4d83-cdd5-5d28-ad3f-41da33a7fd3a",
}
FIELDS = {
    "robot_perception": "5154e719-4836-5bb6-a37a-10bb16e87c9b",
    "embodied_brain": "2b8cfd73-c6ea-5fb5-b73b-5110fa3f3ccc",
    "optical_compute": "0f63b5d7-6855-5685-8cb9-9def613ee01b",
    "solid_battery": "2a77fbc5-923f-582e-b220-4a60ea9d40d8",
    "functional_material": "edc8b06e-95f5-5d50-bc86-eaa6c90b8398",
    "magnetic": "924a6dff-cbc3-5f26-903c-47b714a0d79f",
    "additive": "5d859de7-23c6-55d7-96a8-4a3b03f7a60d",
    "precision_equipment": "ea27f577-3922-5bb8-8d89-986d9b8c9887",
    "ai_bio": "b0144c59-a18b-55e9-a036-a55a3c417fa9",
    "nucleic": "306d0f68-aba6-541d-be30-6351381598b0",
    "new_biologic": "279e5504-daac-52ec-a56f-e3a8337ee5be",
    "life_instruments": "57d47879-d88d-53cf-a4ab-3a84727d9ac2",
    "bci": "04ae0050-2142-5b8c-a9a2-790760e25ed5",
    "quantum_hardware": "9c1a8788-c9ac-52e2-a349-77b64f76ddbd",
}
TOPICS = {
    "embodied_brain": "72a48336-8848-56ea-8482-5f02f9f0468a",
    "optical_interconnect": "e7a67649-76a4-5c5c-94a6-7beef9fd38ee",
    "solid_key": "9c9c85ab-2abf-5df2-984f-6bfb0a6a4d05",
    "magnetic": "3c25a63b-a5ee-5801-9733-a20e9246ba9f",
    "additive": "aa2a14e6-56d3-5b24-b9c2-9f86654dc14e",
    "virtual_cell": "2b7bd851-4d0f-5a32-89f9-423686cf1a11",
    "nucleic": "c8685470-7c65-540e-8875-edc3eae7fd40",
    "bci": "73b2cf7d-8c89-5ca9-ada6-92bd450b82b3",
    "quantum_hardware": "ab9ab50e-c7bf-5760-942d-513d0b3e91c0",
}


def source(article: int, title: str, excerpt: str) -> dict:
    return {"name": "投资界", "title": title, "url": f"https://news.pedaily.cn/202610/{article}.shtml", "excerpt": excerpt}


def item(company: str, day: str, round_original: str, bucket: str, amount: str, investors: str,
         business: str, technology: str, evidence: dict, classification: tuple,
         *, suffix: str = "", status: str = "pending", currency: str | None = None) -> dict:
    stable = str(uuid.uuid5(NAMESPACE, f"{company}|{day}|{round_original}|{suffix}"))
    return {"company": company, "date": day, "round": round_original, "bucket": bucket,
            "amount": amount, "currency": currency, "investors": investors, "business": business,
            "technology": technology, "source": evidence, "classification": classification,
            "stable_event_id": stable, "review_status": status}


E = []
src = source(571137, "天嗅智能获天使+轮融资，国内机器嗅觉产业化基地正式投产",
             "天嗅智能完成天使+轮融资，由杭州市科创集团领投；资金用于嗅觉芯片迭代、智造基地产能和行业场景落地。")
E.append(item("天嗅智能", "2026-10-30", "天使+轮", "early", "未披露", "杭州市科创集团（领投）",
              "机器嗅觉产品与行业解决方案", "嗅觉芯片、嗅觉大模型、气味数据库及电子鼻",
              src, ("new_field_or_topic", "robot", "robot_perception", None, "机器嗅觉芯片与气味感知系统")))
src = source(571105, "四川全固态完成数千万元A轮融资，聚焦固态电池硫化锂材料",
             "四川全固态完成数千万元A轮融资，由红榕资本、明势创投领投；公司已实现硫化锂一步合成工艺突破。")
E.append(item("四川全固态", "2026-10-30", "A轮", "vc", "数千万元人民币",
              "红榕资本、明势创投（领投）；天泓投资、兴湘科创、英诺天使（跟投）",
              "固态电池硫化锂关键材料研发与制造", "硫化锂一步合成、百吨级材料产线",
              src, ("existing_taxonomy", "energy", "solid_battery", "solid_key", None), currency="CNY"))
src = source(571101, "扰动之心完成数千万元融资，探索下一代「生命世界模型」AIDD创新",
             "扰动之心完成数千万元天使轮及天使+轮融资，由清松资本领投，同杨基金及多家药企跟投。")
for rd, suffix in (("天使轮", "angel"), ("天使+轮", "angel_plus")):
    E.append(item("扰动之心", "2026-10-30", rd, "early", "两轮合计数千万元人民币（未拆分）",
                  "清松资本（领投）；同杨基金及多家药企（跟投）", "AI for Science与药物研发",
                  "扰动组学、生命世界模型、虚拟细胞状态推演",
                  src, ("existing_taxonomy", "bio", "ai_bio", "virtual_cell", None), suffix=suffix,
                  status="needs_verification", currency="CNY"))
src = source(571090, "术加医疗完成数千万元A轮融资，深耕妇科临床痛点综合解决方案",
             "术加医疗完成数千万元A轮融资，由山蓝资本独家投资；公司围绕妇科宫腔诊疗构建产品矩阵。")
E.append(item("术加医疗", "2026-10-30", "A轮", "vc", "数千万元人民币", "山蓝资本（独家投资）",
              "妇科有源医疗器械研发、生产与销售", "宫腔组织切割活检与阻抗控制内膜消融",
              src, ("new_field_or_topic", "bio", "life_instruments", None, "妇科微创诊疗与有源医疗器械"), currency="CNY"))
src = source(571071, "星科源完成亿元级Pre-A轮融资，聚焦下一代固态电池专用的纳米硅技术",
             "星科源完成亿元级Pre-A轮融资，由弘毅投资领投；主营固态电池负极及硅基光电器件用纳米硅材料。")
E.append(item("星科源", "2026-10-29", "Pre-A轮", "vc", "亿元级人民币", "弘毅投资（领投）；厦门钨业产业基金、宜宾人才基金（跟投）",
              "固态电池专用纳米硅材料", "自研CVD装备、超细纳米硅、表面改性与二次造粒",
              src, ("existing_taxonomy", "energy", "solid_battery", "solid_key", None), currency="CNY"))
src = source(571068, "考拉悠然完成B++轮融资，持续迭代世界模型基座与多模态大模型",
             "考拉悠然完成B++轮融资，投资方为明文炜业；资金用于世界模型、多模态大模型和具身智能体。")
E.append(item("考拉悠然", "2026-10-29", "B++轮", "vc", "未披露", "明文炜业",
              "世界模型基座与具身智能体", "悠然无界世界模型、Geek Mind具身大脑及硬件抽象层",
              src, ("existing_taxonomy", "robot", "embodied_brain", "embodied_brain", None)))
src = source(571065, "宜诺生物完成超亿元融资，以LNP递送技术为核心",
             "宜诺生物一年内连续完成天使轮和Pre-A轮融资，交易金额超亿元；公司提供mRNA药物端到端CRDMO服务。")
for rd, bucket, suffix in (("天使轮", "early", "angel"), ("Pre-A轮", "vc", "pre_a")):
    E.append(item("宜诺生物", "2026-10-29", rd, bucket, "两轮合计超亿元人民币（未拆分）",
                  "毅达资本、天汇资本（联合领投）；鲁信创投等（跟投）", "mRNA药物CRDMO与LNP递送平台",
                  "RNA序列设计、LNP/tLNP制剂及GMP生产",
                  src, ("existing_taxonomy", "bio", "nucleic", "nucleic", None), suffix=suffix,
                  status="needs_verification", currency="CNY"))
src = source(571063, "博骥源完成数千万元融资，聚焦代谢与炎症性疾病",
             "博骥源完成数千万元A+轮融资，资金用于BGT-010临床开发和创新候选分子验证。")
E.append(item("博骥源", "2026-10-29", "A+轮", "vc", "数千万元人民币", "勤智资本、富汇创投、个人投资人及老股东",
              "代谢与炎症性疾病小分子创新药", "差异化靶点、分子实体创新及GPR84管线",
              src, ("new_field_or_topic", "bio", "new_biologic", None, "小分子创新药与差异化靶点"), currency="CNY"))
src = source(571036, "西安新派得完成数千万元Pre-A轮融资，高纯铌钽产线顺利通产",
             "西安新派得完成数千万元Pre-A轮股权投资，推动高纯难熔金属材料与核心装备国产化。")
E.append(item("西安新派得", "2026-10-29", "Pre-A轮", "vc", "数千万元人民币", "芯能创投、上海科创集团知识产权基金、江苏金桥基金",
              "高纯铌钽难熔金属材料及专用装备", "高纯金属提纯、自研专用装备和AI闭环工艺控制",
              src, ("new_field_or_topic", "energy", "functional_material", None, "高纯难熔金属与智能提纯装备"), currency="CNY"))
src = source(571025, "文远知行子公司「景烁科技」完成数千万美元首轮融资，加速构建物理AI底座",
             "景烁科技获嘉御资本、香港科技园、天狼星资本数千万美元Pre-A轮共同投资。")
E.append(item("景烁科技", "2026-10-29", "Pre-A轮", "vc", "数千万美元", "嘉御资本、HKSTP香港科技园、天狼星资本",
              "物理AI数据与模型基础设施", "WorldEngine数据模型平台、GENESIS-Robotics世界模型及第一视角采集设备",
              src, ("new_field_or_topic", "robot", "embodied_brain", None, "物理AI数据与世界模型基础设施"), currency="USD"))
src = source(571000, "特种运输车企业「伏尔坎」完成数千万元融资",
             "伏尔坎完成数千万元融资，由投控东海投资；公司研发制造面向超限大件的多功能特种运输车辆。")
E.append(item("伏尔坎", "2026-10-28", "轮次未披露", "pending", "数千万元人民币", "投控东海（深投控）",
              "多功能特种运输车辆研发与制造", "超限大件运输的承载、振动控制、姿态稳定和空间适应技术",
              src, ("new_field_or_topic", "equipment", "precision_equipment", None, "特种运输装备与精密载运系统"),
              status="needs_verification", currency="CNY"))
src = source(570976, "百奥几何完成1亿美元A轮系列融资，带队迈向生命科学超级智能",
             "百奥几何完成A+轮融资，A轮系列融资超1亿美元；本轮用于微观世界模型和自动化实验室。")
E.append(item("百奥几何", "2026-10-28", "A+轮", "vc", "A轮系列融资超1亿美元（本轮未单独披露）", "国寿资本（领投）；上海生物医药基金、国开科创、瑞力投资、国方创投、达晨财智等",
              "AI Native生物科技与药物研发", "GeoFlow分子世界模型、GeoCell细胞世界模型及干湿实验闭环",
              src, ("existing_taxonomy", "bio", "ai_bio", "virtual_cell", None), status="needs_verification", currency="USD"))
src = source(570974, "澜昆微电子完成数亿融资，聚焦算力互连赛道",
             "澜昆微连续完成两轮融资，累计数亿元；公司研发高带宽光I/O芯片及芯粒集成方案，报道未披露轮次。")
for rd, suffix, investors in (
    ("轮次未披露（第一轮）", "round_1", "隆湫资本、纪源资本（领投）；老股东追加"),
    ("轮次未披露（第二轮）", "round_2", "光合创投、隆湫资本（领投）；中芯聚源及老股东（跟投）"),
):
    E.append(item("澜昆微电子", "2026-10-28", rd, "pending", "两轮累计数亿元人民币（未拆分）", investors,
                  "AI算力中心光互连芯片与模块", "高带宽光I/O、NPO/CPO芯片、三维光电封装及芯粒集成",
                  src, ("existing_taxonomy", "compute", "optical_compute", "optical_interconnect", None),
                  suffix=suffix, status="needs_verification", currency="CNY"))
src = source(570968, "脑虎科技完成7亿人民币B轮融资，加速「三全」脑机接口产业化",
             "脑虎科技完成7亿元人民币B轮融资，用于全植入、全无线、全功能脑机接口临床和量产。")
E.append(item("脑虎科技", "2026-10-28", "B轮", "vc", "7亿元人民币", "国投聚力、深创投、勤智资本（联合领投）；中芯聚源、黄浦投资、IDG资本等（跟投）",
              "植入式柔性脑机接口研发与产业化", "全植入、全无线、全功能柔性脑机接口系统",
              src, ("existing_taxonomy", "brain", "bci", "bci", None), currency="CNY"))
src = source(570955, "金磁海纳完成数千万元A+轮融资，专注非晶及纳米晶软磁材料",
             "金磁海纳完成数千万元A+轮融资，用于纳米晶磁粉芯产线、产品研发和市场拓展。")
E.append(item("金磁海纳", "2026-10-28", "A+轮", "vc", "数千万元人民币", "澄凯基金（领投）；粤科金融、鸿富资产（跟投/追加）",
              "非晶及纳米晶软磁材料研发制造", "非晶/纳米晶带材、磁芯及软磁合金粉芯",
              src, ("existing_taxonomy", "energy", "magnetic", "magnetic", None), currency="CNY"))
src = source(570924, "恒元光电完成近亿元Pre-A+轮融资，加速铌酸锂晶体产业化",
             "恒元光电完成近亿元Pre-A+轮融资，加速大尺寸光学级铌酸锂晶体产业化。")
E.append(item("恒元光电", "2026-10-27", "Pre-A+轮", "vc", "近亿元人民币", "山东省新动能、山东省财欣投资、源创基金等",
              "光学级铌酸锂晶体研发、生产与销售", "大尺寸铌酸锂晶体及薄膜铌酸锂上游光电材料",
              src, ("new_field_or_topic", "compute", "optical_compute", None, "铌酸锂光电材料与器件基质"), currency="CNY"))
src = source(570922, "乾原量子完成超亿元天使轮融资，深耕中性原子量子超算赛道",
             "乾原量子完成超亿元天使轮融资，12家机构联合投资；采用中性原子QPU与互联路线。")
E.append(item("乾原量子", "2026-10-27", "天使轮", "early", "超亿元人民币", "安徽省、合肥市、高新区国资平台及市场化机构等12家机构",
              "中性原子量子计算基础设施", "中性原子QPU、QAVEXUS互联与量子超算集群",
              src, ("existing_taxonomy", "quantum", "quantum_hardware", "quantum_hardware", None), currency="CNY"))
src = source(570906, "百世达完成天使+轮融资，定义消费级桌面3D打印新形态",
             "百世达年内连续完成天使轮和天使+轮融资，专注消费级及专业级3D打印设备。")
for rd, suffix, investor in (("天使轮", "angel", "高瓴创投（独家投资）"), ("天使+轮", "angel_plus", "静水湖创投（独家投资）")):
    E.append(item("百世达", "2026-10-27", rd, "early", "未披露", investor,
                  "消费级及专业级3D打印设备", "分层覆膜立体光刻、线激光扫描光固化与材料体系",
                  src, ("existing_taxonomy", "equipment", "additive", "additive", None), suffix=suffix))


PEDAILY_RESULTS = {"2026-10-27": (5, 3), "2026-10-28": (6, 5), "2026-10-29": (7, 6),
                   "2026-10-30": (7, 4), "2026-10-31": (0, 0), "2026-11-01": (0, 0)}

RAW_RESULTS = (
    (571137, "2026-10-30", "天嗅智能获天使+轮融资，国内机器嗅觉产业化基地正式投产", "candidate", "天使+轮；中国科技企业"),
    (571123, "2026-10-30", "野人先生宣布与黑蚁资本成为战略合作伙伴", "excluded", "战略合作，不属于目标轮次且科技属性不足"),
    (571105, "2026-10-30", "四川全固态完成数千万元A轮融资，聚焦固态电池硫化锂材料", "candidate", "A轮；中国科技企业"),
    (571101, "2026-10-30", "扰动之心完成数千万元融资，探索下一代生命世界模型AIDD创新", "candidate", "正文明确天使轮及天使+轮"),
    (571098, "2026-10-30", "杭州国资押注，李开复的零一万物加速冲刺IPO", "excluded", "IPO叙事且未披露目标轮次"),
    (571102, "2026-10-30", "湾测完成战略轮融资，持续攻坚核心技术", "excluded", "战略轮不纳入VC或早期统计"),
    (571090, "2026-10-30", "术加医疗完成数千万元A轮融资，深耕妇科临床痛点综合解决方案", "candidate", "A轮；中国科技企业"),
    (571071, "2026-10-29", "星科源完成亿元级Pre-A轮融资，聚焦固态电池纳米硅技术", "candidate", "Pre-A轮；中国科技企业"),
    (571068, "2026-10-29", "考拉悠然完成B++轮融资，持续迭代世界模型基座与多模态大模型", "candidate", "B++轮；中国科技企业"),
    (571065, "2026-10-29", "宜诺生物完成超亿元融资，以LNP递送技术为核心", "candidate", "正文明确天使轮和Pre-A轮"),
    (571063, "2026-10-29", "博骥源完成数千万元融资，聚焦代谢与炎症性疾病", "candidate", "正文明确A+轮"),
    (571036, "2026-10-29", "西安新派得完成数千万元Pre-A轮融资，高纯铌钽产线顺利通产", "candidate", "Pre-A轮；中国科技企业"),
    (571025, "2026-10-29", "文远知行子公司景烁科技完成数千万美元首轮融资", "candidate", "正文明确Pre-A轮"),
    (571022, "2026-10-29", "GreenVoltis完成数千万美元A轮融资", "excluded", "报道明确为瑞典企业，不属于中国科技企业范围"),
    (571000, "2026-10-28", "特种运输车企业伏尔坎完成数千万元融资", "needs_verification", "科技属性明确但轮次未披露"),
    (570997, "2026-10-28", "微纳核芯完成超10亿元C2轮融资", "excluded", "C2轮超出本次目标轮次"),
    (570976, "2026-10-28", "百奥几何完成1亿美元A轮系列融资", "candidate", "正文明确本轮为A+轮"),
    (570974, "2026-10-28", "澜昆微电子完成数亿融资，聚焦算力互连赛道", "needs_verification", "明确两轮融资但均未披露轮次"),
    (570968, "2026-10-28", "脑虎科技完成7亿元人民币B轮融资", "candidate", "B轮；中国科技企业"),
    (570955, "2026-10-28", "金磁海纳完成数千万元A+轮融资", "candidate", "A+轮；中国科技企业"),
    (570934, "2026-10-27", "维发电子完成亿元级C轮融资", "excluded", "C轮超出本次目标轮次"),
    (570924, "2026-10-27", "恒元光电完成近亿元Pre-A+轮融资", "candidate", "Pre-A+轮；中国科技企业"),
    (570922, "2026-10-27", "乾原量子完成超亿元天使轮融资", "candidate", "天使轮；中国科技企业"),
    (570906, "2026-10-27", "百世达完成天使+轮融资", "candidate", "正文明确天使轮和天使+轮"),
    (570881, "2026-10-27", "九识获新华投控战略投资，深耕RoboVan赛道", "excluded", "战略投资不纳入VC或早期统计"),
)


def import_trial() -> dict[str, int]:
    migrate()
    timestamp = now()
    with connect() as connection, connection:
        connection.execute(
            """INSERT INTO v35_collection_batches
               (batch_id,batch_name,period_start,period_end,scope_note,status,source_count,raw_source_count,
                new_candidate_count,duplicate_source_count,effective_event_count,vc_event_count,early_event_count,
                pending_round_count,pending_classification_count,started_at,completed_at,created_by,created_at,updated_at)
               VALUES (?,?,?,?,?,'completed',4,25,22,0,22,12,7,3,22,?,?,?,?,?)
               ON CONFLICT(batch_id) DO UPDATE SET status='completed',source_count=4,raw_source_count=25,
                 new_candidate_count=22,duplicate_source_count=0,effective_event_count=22,vc_event_count=12,
                 early_event_count=7,pending_round_count=3,pending_classification_count=22,
                 completed_at=excluded.completed_at,updated_at=excluded.updated_at""",
            (BATCH_ID, "V3.5首批历史试采", "2026-10-27", "2026-11-01",
             "中国科技全领域；VC成长轮、种子/天使轮；不受V3.2十个一级领域限制。",
             timestamp, timestamp, "codex_v35_trial", timestamp, timestamp),
        )
        connection.execute("DELETE FROM v35_collection_searches WHERE batch_id=?", (BATCH_ID,))
        connection.execute("DELETE FROM v35_collection_search_results WHERE batch_id=?", (BATCH_ID,))
        for day, (raw_count, valid_articles) in PEDAILY_RESULTS.items():
            searches = (
                ("投资界", "融资频道逐日归档；种子/天使/Pre-A/A/A+/A++/Pre-B/B/B+/B++及轮次待核验", raw_count, valid_articles, "completed" if raw_count else "no_result", "正文逐条核验"),
                ("36氪", f"{day} 融资 科技 种子 天使 Pre-A A轮 B轮", 0, 0, "no_result", "公开搜索页未返回可核验的目标日期正文"),
                ("IT桔子", f"{day} 中国科技融资", 0, 0, "failed", "公开入口返回HTTP 412，未绕过访问限制"),
                ("公开网页检索", f"{day} 中国科技公司 完成融资 天使轮 A轮 B轮", 0, 0, "no_result", "筛除上市公司融资融券等非股权融资噪声"),
            )
            for source_name, query, results, valid, status, notes in searches:
                connection.execute(
                    "INSERT INTO v35_collection_searches VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (uid(), BATCH_ID, day, source_name, query, results, valid, status, notes, timestamp),
                )
        for article_id, day, title, status, reason in RAW_RESULTS:
            url = f"https://news.pedaily.cn/202610/{article_id}.shtml"
            connection.execute(
                "INSERT INTO v35_collection_search_results VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid5(NAMESPACE, "result|" + url)), BATCH_ID, "投资界", title, url,
                 day, status, reason, timestamp),
            )
        for row in E:
            candidate_id = str(uuid.uuid5(NAMESPACE, "candidate|" + row["stable_event_id"]))
            connection.execute(
                """INSERT OR IGNORE INTO v35_historical_candidates
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (candidate_id, BATCH_ID, row["stable_event_id"], row["company"], row["date"], None,
                 row["round"], row["bucket"], row["amount"], row["currency"], row["investors"],
                 row["business"], row["technology"], "B", row["review_status"],
                 "codex_v35_trial", timestamp, timestamp),
            )
            evidence = row["source"]
            digest = hashlib.sha256((evidence["title"] + "\n" + evidence["excerpt"]).encode()).hexdigest()
            connection.execute(
                """INSERT OR IGNORE INTO v35_candidate_sources
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid5(NAMESPACE, candidate_id + "|" + evidence["url"])), candidate_id,
                 evidence["name"], evidence["title"], evidence["url"], row["date"], evidence["excerpt"],
                 1, "accessible", digest, timestamp),
            )
            ptype, industry_key, field_key, topic_key, proposed_topic = row["classification"]
            connection.execute(
                """INSERT OR IGNORE INTO v35_classification_proposals
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid5(NAMESPACE, "proposal|" + candidate_id)), candidate_id, ptype,
                 None, None, proposed_topic, INDUSTRIES[industry_key], FIELDS[field_key],
                 TOPICS[topic_key] if topic_key else None, row["technology"],
                 "沿用V3.2一级产业；若为新主题，仅扩展技术边界，不改变冻结一级分类。",
                 ("企业产品和核心技术可直接匹配V3.2现有主题。" if ptype == "existing_taxonomy"
                  else "现有一级和二级领域可容纳企业，但当前三级主题不能准确表达其产品级技术。"),
                 1, 1, "pending", "codex_v35_trial", timestamp),
            )
        exists = connection.execute(
            "SELECT 1 FROM audit_logs WHERE action='import_v35_trial_backfill' AND entity_id=?", (BATCH_ID,)
        ).fetchone()
        if not exists:
            summary = {"raw_articles": 25, "candidate_articles": 18, "candidate_events": 22,
                       "vc": 12, "early": 7, "pending_round": 3, "new_topic_proposals": 7,
                       "new_industry_proposals": 0}
            connection.execute(
                "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uid(), "codex_v35_trial", "import_v35_trial_backfill", "v35_collection_batch", BATCH_ID,
                 None, json.dumps(summary, ensure_ascii=False),
                 "Six-day all-technology historical trial; candidate and taxonomy proposal layers only.", None, timestamp),
            )
    return {"candidates": len(E), "vc": sum(x["bucket"] == "vc" for x in E),
            "early": sum(x["bucket"] == "early" for x in E),
            "pending_round": sum(x["bucket"] == "pending" for x in E)}


if __name__ == "__main__":
    print(json.dumps(import_trial(), ensure_ascii=False))
