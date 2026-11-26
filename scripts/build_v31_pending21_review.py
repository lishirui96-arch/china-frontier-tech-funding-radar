from __future__ import annotations

import json
import uuid
from csv import DictWriter
from datetime import datetime, timezone
from pathlib import Path

from funding_radar.db import transaction


NS = uuid.UUID("fd0af20c-ce77-4ccc-ae38-214e904e771d")
NOW = datetime.now(timezone.utc).isoformat()


def uid(kind: str, value: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{value}"))


REVIEWS = [
    ("广荣科技", "聚焦中老年认知健康与心脑慢病全周期管理的AI健康科技企业", "认知健康筛查、个性化循证干预和随访平台", "AI全链路引擎、认知症筛查、数字化循证干预", "正文明确公司构建筛查—干预—随访闭环，并称其为AI健康科技企业", "生物制造与生命科学", "数字健康与AI医疗", "认知健康筛查与数字干预", "new_field", "high", "主营产品属于医疗健康服务数字化；与脑科学存在交叉，但主要商业产品是健康筛查和干预平台"),
    ("云脉芯联", "面向云数据中心和AI智算集群研发网络互联芯片", "智能网卡、DPU及AI集群网络产品", "400Gbps网络互联、RDMA、数据处理器和集群网络虚拟化", "正文直接列出网络互联芯片、智能网卡和DPU产品", "AI计算与半导体", "AI算力基础设施", "AI集群网络互联芯片与智能网卡", "new_topic", "high", "产品处于AI集群网络基础设施与半导体交界，现有一级和二级足以容纳"),
    ("原力无限INFIFORCE", "待补充", "待补充", "待补充", "现有来源页面仅保留融资标题，未提供可核验的主营业务、产品或技术正文", None, None, None, "pending", "unclassified", "不得依据企业名称或融资标题推断技术分类"),
    ("乎灵科技", "面向个人用户开发可穿戴AI助理", "AI语音健康戒指", "语音采集转写、任务与日程抽取、可穿戴端侧交互算法", "正文将产品定义为可穿戴AI助手并列出语音记录、转写和任务提取功能", "AI软件与工业智能", "个人AI与智能交互", "可穿戴语音AI助手", "new_field", "high", "属于个人AI交互与智能终端，不需要新增一级产业"),
    ("CataX AI", "以AI智能体加速药物临床前和早期临床开发", "Clinical-of-One研发工作流与临床开发智能体", "智能体文档生成、数据处理和临床运营自动化", "正文明确其重点不是靶点或分子发现，而是临床前及早期临床开发", "生物制造与生命科学", "AI驱动的生命科学", "AI智能体驱动的临床开发", "new_topic", "high", "可直接归入现有AI驱动生命科学二级领域，但应区别于AI药物分子设计"),
    ("稳准智能", "为工业和科学结构化数据提供大模型与决策系统", "LimiX-2结构化数据基础模型", "大数据模型、因果学习、稳定学习、表格和传感器时序建模", "正文明确处理表格、传感器时序和流程台账等结构化数据", "AI软件与工业智能", "大模型基础能力", "结构化数据大模型与因果学习", "new_topic", "high", "现有一级、二级适用，需新增更准确的三级主题"),
    ("赛恩领动", "研发面向汽车及物理智能场景的高性能雷达感知系统", "4D成像雷达软硬件产品", "雷达芯片与硬件、传感算法、端到端AI雷达基础模型", "正文明确公司同时研发4D成像雷达硬件、感知算法和端到端AI模型", "高端装备与先进制造", "智能传感与空间感知", "4D成像雷达与端到端感知", "new_field", "high", "产品横跨汽车与机器人，按底层传感装备归类可避免误限于机器人场景"),
    ("亦立医药", "开发创新放射性药物管线", "放射性药物候选管线", "核素药物研发及临床转化", "正文明确资金用于放射性药物管线的临床前、IND和早期临床开发", "生物制造与生命科学", "新型生物药", "放射性药物与核素诊疗", "new_topic", "medium", "现有一级适用；当前企业数不足以单设二级，可先在新型生物药下建立主题"),
    ("飞拓星驰", "开发家庭AI互动娱乐系统", "家庭AI游戏机和体感互动内容", "AI游戏引擎、端侧人体3D姿态模型、空间感知与实时交互", "正文列明AI游戏引擎、端侧模型、家庭娱乐硬件和高帧率3D姿态映射", "AI软件与工业智能", "个人AI与智能交互", "家庭体感AI与互动娱乐", "new_field", "high", "消费级空间交互产品可并入个人AI与智能交互，不需新增一级产业"),
    ("3Chat.ai", "为企业营销、销售和客户运营提供大模型服务", "客户运营大模型", "企业大模型、客户运营智能体和商业化流程自动化", "正文明确融资用于客户运营大模型训练及规模化获客", "AI软件与工业智能", "企业AI与智能体", "客户运营智能体与销售自动化", "new_topic", "medium", "产品方向清晰但来源对具体技术架构描述有限"),
    ("清析智研", "以AI for Science建设材料研发和表征自动化平台", "AI原生科学仪器、材料CRO与材料IP产品线", "XRD/电镜/拉曼/XPS/NMR表征模型、自主测量和AI实验室", "正文列出三条产品线及多类材料表征模型和自主实验室能力", "高端装备与先进制造", "高端检测与工业装备", "AI原生科学仪器与自主实验室", "new_topic", "high", "主要产品是科学仪器与实验室装备，材料研发作为应用场景和交叉标签"),
    ("知驿科技", "为AI原生企业提供协作基础设施", "企业AI网关与长时经验记忆系统", "Agent协作、授权共享、结构化团队记忆和模型中立接入", "正文明确首款产品围绕企业AI网关、Agent协作及长时经验记忆", "AI软件与工业智能", "企业AI与智能体", "企业智能体与工业知识闭环", "existing", "high", "可直接进入现有企业AI与智能体及既有三级主题"),
    ("原方智能", "研发家庭场景通用机器人", "家庭机器人", "世界模型、真实环境学习与具身控制", "正文明确以世界模型支撑家庭机器人并进行真实世界验证", "机器人与具身智能", "具身智能与自主作业", "通用人形与服务具身系统", "existing", "high", "现有三级主题能够覆盖"),
    ("津工能源", "研发和量产钠离子电池关键材料", "钠离子电池正极材料", "钠电正极材料配方与万吨级制造工艺", "正文明确建设万吨级钠离子电池正极材料产线并面向储能等场景", "新能源与先进材料", "新能源关键材料", "钠离子电池正极材料", "new_topic", "high", "现有一级、二级适用，仅缺少对应三级主题"),
    ("华赛伯曼", "研发面向实体瘤的创新细胞治疗药物", "TIL细胞药物", "肿瘤浸润淋巴细胞制备和精准细胞治疗", "正文明确公司推进实体瘤TIL细胞药物", "生物制造与生命科学", "细胞治疗", "细胞工程与精准细胞治疗", "existing", "high", "与现有主题边界一致"),
    ("自然选择", "开发面向个人用户的AI伴侣与智能社交产品", "EVE 3D AI伴侣、Elys智能体社交网络", "长期记忆、人格交互、3D数字角色与Agent社交", "正文明确两款产品及人与AI长期关系定位", "AI软件与工业智能", "个人AI与智能交互", "AI伴侣与智能社交网络", "new_field", "high", "个人AI产品形态可并入现有AI一级方向，但现有二级目录缺口明显"),
    ("犀燃医疗", "研发眼科手术设备与耗材", "超声乳化、玻切、激光玻切和眼科OCT设备", "眼科显微手术能量控制、成像与设备系统集成", "正文直接列出多类眼科手术主机、OCT和配套耗材", "生物制造与生命科学", "生命科学仪器", "高端眼科手术设备", "new_topic", "high", "现有二级可容纳，需区别于临床检测仪器"),
    ("邦芯半导体", "研发半导体晶圆制造前道装备", "刻蚀、去胶和薄膜沉积设备", "6/8/12英寸晶圆刻蚀、光刻胶去除与薄膜工艺", "正文明确产品覆盖刻蚀、去胶、薄膜沉积及多尺寸晶圆", "AI计算与半导体", "半导体装备与先进封装", "半导体前道刻蚀与薄膜设备", "new_topic", "high", "可直接归入已建立但尚缺三级主题的半导体装备二级领域"),
    ("希格生科", "推进肿瘤创新药及心肾疾病药物管线", "肿瘤、心脏和肾脏疾病候选药物管线", "现有来源未披露具体药物模态和核心平台技术", "正文仅确认管线治疗领域和临床推进用途，未说明产品模态", "生物制造与生命科学", "新型生物药", None, "existing", "low", "可确定一级和宽口径二级；三级必须等待药物模态或技术平台证据"),
    ("赛尔智控", "研发三维空间采集与测量设备", "3D空间相机、手持式3D激光扫描仪", "固态激光雷达小型化、3D Gaussian Splatting、SLAM和边缘AI", "正文明确两类硬件产品及激光雷达、三维重建和SLAM技术", "高端装备与先进制造", "智能传感与空间感知", "三维空间相机与激光扫描", "new_field", "high", "与赛恩领动共享空间感知底层技术，但产品和应用边界不同"),
    ("超球面科技", "研发组合式基础模型与模型编排平台", "Infinite Models全栈技术", "专家模型分化、调度编排和持续协同进化", "正文明确以大基座模型调度大量专业化专家模型的组合式缩放范式", "AI软件与工业智能", "大模型基础能力", "多模型专家系统与模型编排", "new_topic", "high", "现有一级、二级适用，需新增三级主题表达其组合模型路线"),
]


EXTENSIONS = [
    ("生物制造与生命科学", "数字健康与AI医疗", None, None, ["广荣科技"], "现有生命科学二级领域均偏药物或仪器，不能准确表达AI健康筛查和数字干预产品"),
    ("AI软件与工业智能", "个人AI与智能交互", None, None, ["乎灵科技", "飞拓星驰", "自然选择"], "三家企业均面向个人用户的人机交互，但产品分别为可穿戴助手、体感娱乐和AI伴侣"),
    ("高端装备与先进制造", "智能传感与空间感知", None, None, ["赛恩领动", "赛尔智控"], "两家企业共同提供物理空间感知硬件与算法，覆盖4D雷达和三维激光扫描"),
]


def main() -> None:
    with transaction() as db:
        records = {row["company_name_standard"]: dict(row) for row in db.execute("SELECT * FROM v30_historical_records")}
        for item in REVIEWS:
            company, business, products, tech, excerpt, industry, field, topic, fit, confidence, basis = item
            record = records[company]
            db.execute(
                """INSERT OR REPLACE INTO v31_pending_classification_reviews
                (review_id,record_id,company_name,source_url,source_title,business_summary,product_summary,technology_summary,
                 evidence_excerpt,proposed_industry_name,proposed_field_name,proposed_topic_name,taxonomy_fit,
                 classification_confidence,classification_basis,needs_manual_review,review_status,created_at,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uid("review", company), record["record_id"], company, record["source_url"],
                 json.loads(record["source_snapshot_json"]).get("source_title", ""), business, products, tech, excerpt,
                 industry, field, topic, fit, confidence, basis, 1, "proposed", NOW, "codex_v3_1_research"),
            )
        for industry, field, parent_field, topic, companies, reason in EXTENSIONS:
            key = f"{industry}|{field}|{parent_field}|{topic}"
            db.execute(
                """INSERT OR REPLACE INTO v31_taxonomy_extension_proposals
                (proposal_id,parent_industry_name,proposed_field_name,parent_field_name,proposed_topic_name,
                 supporting_companies_json,proposal_reason,review_status,created_at,created_by)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (uid("extension", key), industry, field, parent_field, topic, json.dumps(companies, ensure_ascii=False),
                 reason, "pending", NOW, "codex_v3_1_research"),
            )
        review_rows = [dict(row) for row in db.execute(
            "SELECT * FROM v31_pending_classification_reviews ORDER BY company_name"
        )]
        extension_rows = [dict(row) for row in db.execute(
            "SELECT * FROM v31_taxonomy_extension_proposals ORDER BY parent_industry_name, proposed_field_name"
        )]
    docs = Path(__file__).resolve().parents[1] / "docs"
    csv_path = docs / "V31_21条待分类来源复核.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = DictWriter(fh, fieldnames=review_rows[0].keys())
        writer.writeheader()
        writer.writerows(review_rows)

    fit_labels = {"existing": "现有目录可容纳", "new_field": "建议新增二级", "new_topic": "建议新增三级", "pending": "证据不足待核实"}
    lines = [
        "# V3.1 21条待分类融资记录来源复核报告",
        "",
        "> 本报告是V3.1独立建议层，不修改V3.0冻结分类，不改变融资事件审核状态，也不更新正式Release。",
        "",
        "## 总体结论",
        "",
        "- 现有10个一级产业方向足以容纳目前有产品证据的企业，不建议增加第11个一级方向。",
        "- 21条记录中，20条已能确定一级和二级建议方向；原力无限INFIFORCE的来源正文不足，继续待分类。",
        "- 建议在现有一级方向下新增3个二级领域：数字健康与AI医疗、个人AI与智能交互、智能传感与空间感知。",
        "- 4条可直接使用现有三级目录，10条适合在现有二级下新增更具体的三级主题，6条涉及新增二级领域。",
        "- 希格生科只能确认到一级和宽口径二级，因来源未披露药物模态，三级暂留空。",
        "",
        "## 二级领域增量建议",
        "",
        "| 现有一级产业 | 建议新增二级领域 | 支持企业 | 理由 |",
        "|---|---|---|---|",
    ]
    for row in extension_rows:
        companies = "、".join(json.loads(row["supporting_companies_json"]))
        lines.append(f'| {row["parent_industry_name"]} | {row["proposed_field_name"]} | {companies} | {row["proposal_reason"]} |')
    lines += [
        "",
        "## 逐条复核",
        "",
        "| 企业 | 主营业务/产品 | 一级分类 | 二级分类 | 三级分类 | 目录处理 | 置信度 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in review_rows:
        summary = f'{row["business_summary"]}；{row["product_summary"]}'
        lines.append(
            f'| [{row["company_name"]}]({row["source_url"]}) | {summary} | '
            f'{row["proposed_industry_name"] or "待分类"} | {row["proposed_field_name"] or "待分类"} | '
            f'{row["proposed_topic_name"] or "待补充"} | {fit_labels[row["taxonomy_fit"]]} | '
            f'{row["classification_confidence"]} |'
        )
    lines += [
        "",
        "## 口径说明",
        "",
        "分类依据来自现有融资来源正文中的企业介绍、产品和技术描述。融资金额、投资方和新闻标题中的热门词不作为技术分类依据。新增二级与三级均为待人工确认建议；V3.0的10→38→34冻结目录保持不变。",
    ]
    (docs / "V31_PENDING21_CLASSIFICATION_REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Seeded {len(REVIEWS)} reviews and {len(EXTENSIONS)} field proposals")


if __name__ == "__main__":
    main()
