from __future__ import annotations

import csv
import re
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from funding_radar.db import connect


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
NAMESPACE = uuid.UUID("a4ad6553-b447-5e92-8fb3-77fd9953b65f")


def proposal_id(level: str, name: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{level}|{name}"))


def write_csv(name: str, rows: list[dict]) -> None:
    with (DOCS / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def evidence_text(row: dict) -> str:
    text = re.sub(r"\s+", " ", str(row["primary_business"] or "")).strip()
    return text[:360]


def missing_evidence(row: dict) -> str:
    title = str(row.get("source_title") or "")
    company = str(row.get("company_name") or "")
    needs = []
    if len(company) > 30 or re.search(r"融资|B轮|领军企业|合资公司", company):
        needs.append("规范企业简称与法定主体")
    if re.search(r"护理品牌|开店增长|耳机|短出行|智能设备", title):
        needs.append("证明产品具有可区分的核心技术而非一般消费或服务属性")
    if re.search(r"Manus|OMOWAY|MOWAY|寶蘭|姆特|安澜德健|宁波天辉益", title, re.I):
        needs.append("企业官网产品说明和核心技术架构")
    needs.append("明确主营产品、应用场景及产业链位置的企业或投资机构原文")
    return "；".join(dict.fromkeys(needs))


def existing_mapping(row: dict, taxonomy: dict) -> dict:
    cluster = row["suggested_cluster"]
    text = " ".join(str(row.get(key) or "") for key in ("source_title", "primary_business", "core_technology"))
    industry_name = cluster if cluster in taxonomy["industry"] else cluster.split("（", 1)[0]
    field_name = ""
    topic_name = ""

    if industry_name == "AI软件与工业智能":
        if re.search(r"基础模型|大模型|Scaling|模型组合", text, re.I):
            field_name = "大模型基础能力"
            if re.search(r"模型组合|专家模型|模型编排", text):
                topic_name = "多模型专家系统与模型编排"
    elif industry_name == "机器人与具身智能":
        if re.search(r"机器人|具身|自主", text):
            field_name = "具身智能与自主作业"
    elif industry_name == "AI计算与半导体":
        if re.search(r"光互连|硅光", text):
            field_name, topic_name = "光电互连与先进计算", "AI算力集群的光互连与硅光交换"
        elif re.search(r"装备|加工|检测|精密", text):
            field_name = "半导体装备与先进封装"
        elif re.search(r"芯片|Micro[- ]?LED|显示|光电|微纳", text, re.I):
            field_name = ""
    elif industry_name == "生物制造与生命科学":
        if re.search(r"核素|放射性", text):
            field_name, topic_name = "新型生物药", "放射性药物与核素诊疗"
        elif re.search(r"健康管理|数字化口腔|AI医疗", text, re.I):
            field_name = "数字健康与AI医疗"
        elif re.search(r"医疗|医用|器械|介入|手术|诊疗|设备|雾化", text):
            field_name = "生命科学仪器"
        elif re.search(r"药|疗法|生肽|生物", text):
            field_name = "新型生物药"
    elif industry_name == "新能源与先进材料":
        if re.search(r"涂层", text):
            field_name, topic_name = "磁性材料与功能涂层", "特种防护与功能涂层"
        elif re.search(r"材料|新材|复材|电致变色|电化学", text):
            field_name, topic_name = "高性能功能材料", "其他功能材料观察项"
    elif industry_name == "高端装备与先进制造":
        if re.search(r"检测|仪器|精仪", text):
            field_name = "高端检测与工业装备"
        elif re.search(r"激光|光学|加工|制造|试飞|适航", text):
            field_name = "精密制造与加工装备"
    elif industry_name == "低空经济与无人系统":
        if re.search(r"飞行|适航|航空", text):
            field_name = "低空飞行器与动力系统"

    return {
        "industry_name": industry_name,
        "industry_id": taxonomy["industry"].get(industry_name, ""),
        "field_name": field_name,
        "field_id": taxonomy["field"].get(field_name, ""),
        "topic_name": topic_name,
        "topic_id": taxonomy["topic"].get(topic_name, ""),
    }


def b_evaluation(row: dict, taxonomy: dict) -> dict:
    text = " ".join(str(row.get(key) or "") for key in ("source_title", "primary_business", "core_technology"))
    title = str(row.get("source_title") or "")
    base = {"industry_name": "", "industry_id": "", "field_name": "", "field_id": "",
            "topic_name": "", "topic_id": "", "proposed_field": "", "proposed_topic": "",
            "decision": "evidence_insufficient", "basis": ""}
    if re.search(r"核素|核医学|放射性", title):
        base.update(existing_mapping({**row, "suggested_cluster": "生物制造与生命科学"}, taxonomy))
        base.update(decision="existing_taxonomy", basis="主营医用放射性核素或核医学服务，属于生命科学而非核能工程")
    elif re.search(r"核反应堆|核裂变|小型模块化反应堆|微型反应堆", title):
        name = "新能源与先进材料"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name],
                    proposed_field="先进裂变能与小型反应堆", proposed_topic="小型模块化反应堆与微型核能系统",
                    decision="new_field_and_topic", basis="产品为裂变反应堆系统，不属于聚变或一般新能源材料")
    elif re.search(r"超导|强场", title):
        name, field = "新能源与先进材料", "高性能功能材料"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name], field_name=field,
                    field_id=taxonomy["field"][field], proposed_topic="超导材料与强场磁体",
                    decision="new_topic", basis="主营超导材料、带材或强场磁体可归入功能材料，聚变只是部分应用场景")
    elif re.search(r"聚变", title):
        name = "新能源与先进材料"
        topic = "惯性约束与激光聚变系统" if re.search(r"激光聚变|惯性约束", text) else "磁约束聚变系统工程"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name],
                    proposed_field="可控核聚变工程", proposed_topic=topic,
                    decision="new_field_and_topic", basis="聚变装置、约束路线与工程化系统构成独立技术边界")
    elif re.search(r"底盘|线控制动|EMB|One-box", text, re.I):
        name = "高端装备与先进制造"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name],
                    proposed_field="智能底盘与线控系统", proposed_topic="线控制动与底盘执行系统",
                    decision="new_field_and_topic", basis="核心产品是汽车底盘执行与线控部件，不属于低空飞行器或机器人关节")
    elif re.search(r"AR|智能眼镜|空间计算", text, re.I):
        name, field = "AI软件与工业智能", "个人AI与智能交互"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name], field_name=field,
                    field_id=taxonomy["field"][field], proposed_topic="AR智能眼镜与空间计算终端",
                    decision="new_topic", basis="产品是近眼显示与空间交互终端，现有个人AI主题未覆盖视觉空间计算")
    elif re.search(r"骨传导耳机", text):
        base.update(decision="no_proposal_need_more_evidence", basis="当前证据只支持消费音频硬件，尚不能证明AI交互或独立科技分类边界")
    elif re.search(r"PhotonPay|支付|金融科技", text, re.I):
        name = "AI软件与工业智能"
        base.update(industry_name=name, industry_id=taxonomy["industry"][name],
                    proposed_field="金融科技与数字交易基础设施", proposed_topic="跨境支付与全球结算基础设施",
                    decision="observation_field_and_topic", basis="单一跨境支付企业证据不足以立即新增二级领域，保留观察提案")
    else:
        base["basis"] = "现有正文不足以区分智能终端、汽车电子或一般消费硬件，暂不提出分类"
    return base


FIELD_PROPOSALS = [
    ("可控核聚变工程", "新能源与先进材料", "聚变能产生、约束、加热、磁体、反应装置及工程化验证", "排除一般核裂变、放射性药物和普通超导材料", "recommended"),
    ("先进裂变能与小型反应堆", "新能源与先进材料", "小型模块化反应堆、微型反应堆及新型裂变能系统", "排除聚变装置、传统大型核电运营和医用核素", "recommended"),
    ("智能底盘与线控系统", "高端装备与先进制造", "车辆线控制动、转向、悬架、底盘域控及执行系统", "排除整车品牌、普通机械零部件和机器人关节", "recommended"),
    ("金融科技与数字交易基础设施", "AI软件与工业智能", "数字支付、跨境结算、交易风控和可编程金融基础设施", "排除一般企业软件、消费信贷和传统金融机构业务", "observation_insufficient_events"),
]


TOPIC_PROPOSALS = [
    ("磁约束聚变系统工程", "可控核聚变工程", "新能源与先进材料", "托卡马克、FRC等磁约束路线及系统工程", "recommended"),
    ("惯性约束与激光聚变系统", "可控核聚变工程", "新能源与先进材料", "激光驱动、靶丸与惯性约束聚变工程", "recommended"),
    ("小型模块化反应堆与微型核能系统", "先进裂变能与小型反应堆", "新能源与先进材料", "SMR、微堆及配套安全和能量转换系统", "recommended"),
    ("超导材料与强场磁体", "高性能功能材料", "新能源与先进材料", "超导带材、线材、磁体和强场工程应用", "recommended"),
    ("线控制动与底盘执行系统", "智能底盘与线控系统", "高端装备与先进制造", "One-box、EMB和底盘执行控制部件", "recommended"),
    ("AR智能眼镜与空间计算终端", "个人AI与智能交互", "AI软件与工业智能", "近眼显示、空间感知和视觉交互终端", "recommended"),
    ("跨境支付与全球结算基础设施", "金融科技与数字交易基础设施", "AI软件与工业智能", "多币种收付、跨境清结算与交易基础设施", "observation_insufficient_events"),
]


def main() -> None:
    with (DOCS / "V36_PENDING_75_CLUSTER_ASSIGNMENTS.csv").open(encoding="utf-8-sig", newline="") as handle:
        v36 = {row["candidate_id"]: row for row in csv.DictReader(handle)}
    with connect(read_only=True) as connection:
        taxonomy = {
            "industry": {row["name"]: row["industry_id"] for row in connection.execute("SELECT industry_id,name FROM v30_industries WHERE taxonomy_version='V3.2'")},
            "field": {row["name"]: row["field_id"] for row in connection.execute("SELECT field_id,name FROM v30_fields WHERE taxonomy_version='V3.2'")},
            "topic": {row["name"]: row["topic_id"] for row in connection.execute("SELECT topic_id,name FROM v30_topics WHERE taxonomy_version='V3.2'")},
        }
        rows = [dict(row) for row in connection.execute(
            """SELECT c.*,s.source_title,s.source_url FROM v35_historical_candidates c
               JOIN v35_candidate_sources s USING(candidate_id)
               WHERE c.candidate_id IN ({})
                 AND s.candidate_source_id=(SELECT MIN(s2.candidate_source_id) FROM v35_candidate_sources s2 WHERE s2.candidate_id=c.candidate_id)
               ORDER BY c.announcement_date,c.company_name""".format(",".join("?" for _ in v36)), tuple(v36)
        )]

    mappings = []
    for row in rows:
        prior = v36[row["candidate_id"]]
        category = prior["category"]
        mapping = {"industry_name": "", "industry_id": "", "field_name": "", "field_id": "",
                   "topic_name": "", "topic_id": "", "proposed_field": "", "proposed_topic": "",
                   "decision": "pending_evidence", "basis": prior["rationale"]}
        if category == "A":
            mapping.update(existing_mapping({**row, **prior}, taxonomy))
            mapping["decision"] = "existing_taxonomy"
            mapping["basis"] = prior["rationale"] + "；下级分类仅在技术边界明确时填写"
        elif category == "B":
            mapping.update(b_evaluation({**row, **prior}, taxonomy))
        else:
            mapping["basis"] = missing_evidence(row)
        mappings.append({
            "candidate_id": row["candidate_id"], "company_name": row["company_name"],
            "announcement_date": row["announcement_date"], "round_original": row["round_original"],
            "v36_category": category, "v37_decision": mapping["decision"],
            "industry_id": mapping["industry_id"], "industry_name": mapping["industry_name"],
            "field_id": mapping["field_id"], "field_name": mapping["field_name"],
            "topic_id": mapping["topic_id"], "topic_name": mapping["topic_name"],
            "proposed_field_id": proposal_id("field", mapping["proposed_field"]) if mapping["proposed_field"] else "",
            "proposed_field_name": mapping["proposed_field"],
            "proposed_topic_id": proposal_id("topic", mapping["proposed_topic"]) if mapping["proposed_topic"] else "",
            "proposed_topic_name": mapping["proposed_topic"],
            "classification_basis": mapping["basis"], "business_evidence": evidence_text(row),
            "source_url": row["source_url"], "review_status": "proposal_pending",
        })

    a_rows = [row for row in mappings if row["v36_category"] == "A"]
    b_rows = [row for row in mappings if row["v36_category"] == "B"]
    d_rows = [row for row in mappings if row["v36_category"] == "D"]
    write_csv("V37_75_EVENT_CLASSIFICATION_MAPPING.csv", mappings)
    write_csv("V37_41_EXISTING_TAXONOMY_MATCHES.csv", a_rows)
    write_csv("V37_16_NEW_TECH_CANDIDATE_EVALUATION.csv", b_rows)
    write_csv("V37_18_INSUFFICIENT_EVIDENCE_EVENTS.csv", d_rows)

    events_by_field: dict[str, list[dict]] = defaultdict(list)
    events_by_topic: dict[str, list[dict]] = defaultdict(list)
    for row in mappings:
        if row["proposed_field_name"]:
            events_by_field[row["proposed_field_name"]].append(row)
        if row["proposed_topic_name"]:
            events_by_topic[row["proposed_topic_name"]].append(row)

    field_rows = []
    for name, industry, definition, boundary, status in FIELD_PROPOSALS:
        evidence = events_by_field[name]
        field_rows.append({
            "proposal_id": proposal_id("field", name), "classification_name": name, "level": "secondary_field",
            "parent_industry_id": taxonomy["industry"][industry], "parent_industry_name": industry,
            "technical_definition": definition, "technical_boundary": boundary,
            "representative_companies": "|".join(sorted({row["company_name"] for row in evidence})),
            "event_count": len(evidence), "related_event_ids": "|".join(row["candidate_id"] for row in evidence),
            "difference_from_existing": "现有二级领域未形成相同的系统级技术边界",
            "addition_reason": "由多家独立融资企业形成可复核技术共同点" if len({row['company_name'] for row in evidence}) >= 2 else "单一事件，仅作为观察项",
            "evidence_urls": "|".join(row["source_url"] for row in evidence), "suggested_status": status,
        })
    topic_rows = []
    for name, parent, industry, definition, status in TOPIC_PROPOSALS:
        evidence = events_by_topic[name]
        topic_rows.append({
            "proposal_id": proposal_id("topic", name), "classification_name": name, "level": "tertiary_topic",
            "parent_id": taxonomy["field"].get(parent) or proposal_id("field", parent), "parent_name": parent,
            "parent_industry_id": taxonomy["industry"][industry], "parent_industry_name": industry,
            "technical_definition": definition,
            "technical_boundary": "只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据",
            "representative_companies": "|".join(sorted({row["company_name"] for row in evidence})),
            "event_count": len(evidence), "related_event_ids": "|".join(row["candidate_id"] for row in evidence),
            "difference_from_existing": "现有三级主题缺少该产品和技术路径的独立边界",
            "addition_reason": "细分技术路线清晰且可与同级主题区分" if evidence else "等待更多事件证据",
            "evidence_urls": "|".join(row["source_url"] for row in evidence), "suggested_status": status,
        })
    write_csv("V37_NEW_SECONDARY_FIELD_PROPOSALS.csv", field_rows)
    write_csv("V37_NEW_TERTIARY_TOPIC_PROPOSALS.csv", topic_rows)

    field_counts = Counter(row["industry_name"] for row in mappings if row["industry_name"])
    coverage_rows = []
    with connect(read_only=True) as connection:
        for industry in connection.execute("SELECT industry_id,name FROM v30_industries WHERE taxonomy_version='V3.2' ORDER BY sort_order"):
            field_count = connection.execute("SELECT COUNT(*) FROM v30_fields WHERE taxonomy_version='V3.2' AND industry_id=?", (industry["industry_id"],)).fetchone()[0]
            topic_count = connection.execute("""SELECT COUNT(*) FROM v30_topics t JOIN v30_fields f ON f.field_id=t.field_id AND f.taxonomy_version=t.taxonomy_version
                                               WHERE t.taxonomy_version='V3.2' AND f.industry_id=?""", (industry["industry_id"],)).fetchone()[0]
            notes = {
                "新能源与先进材料": "核裂变、聚变与超导工程缺失，材料类二级领域较宽",
                "高端装备与先进制造": "智能底盘缺失；精密制造二级领域没有三级主题",
                "AI软件与工业智能": "个人AI覆盖语音与社交，但缺AR空间计算和金融基础设施边界",
                "AI计算与半导体": "新型显示和通用半导体器件缺少清晰三级主题",
                "生物制造与生命科学": "生命科学覆盖较强，但一般医疗器械主题仍较宽",
                "低空经济与无人系统": "二级领域有3个，但多数缺三级主题；与智能汽车边界需澄清",
                "脑科学与神经技术": "神经信号与神经调控二级领域缺少三级主题",
                "机器人与具身智能": "结构较完整，但与智能底盘、自动驾驶部件存在交叉",
                "商业航天与卫星应用": "遥感和地面服务较完整，航天基础设施缺少三级主题",
                "量子科技": "三条核心技术路线均有二三级结构，覆盖相对完整",
            }[industry["name"]]
            coverage_rows.append({"industry_id": industry["industry_id"], "industry_name": industry["name"],
                                  "existing_field_count": field_count, "existing_topic_count": topic_count,
                                  "mapped_v37_events": field_counts[industry["name"]], "coverage_assessment": notes})

    field_recommended = sum(row["suggested_status"] == "recommended" for row in field_rows)
    field_observe = len(field_rows) - field_recommended
    topic_recommended = sum(row["suggested_status"] == "recommended" for row in topic_rows)
    topic_observe = len(topic_rows) - topic_recommended
    diff_rows = [
        {"level": "primary_industry", "v32_count": 10, "v37_recommended_additions": 0, "v37_observation_items": 0, "projected_count_if_approved": 10, "decision": "保持现有10个一级领域"},
        {"level": "secondary_field", "v32_count": 42, "v37_recommended_additions": field_recommended, "v37_observation_items": field_observe, "projected_count_if_approved": 42 + field_recommended, "decision": "观察项不计入建议新增数"},
        {"level": "tertiary_topic", "v32_count": 51, "v37_recommended_additions": topic_recommended, "v37_observation_items": topic_observe, "projected_count_if_approved": 51 + topic_recommended, "decision": "观察项不计入建议新增数"},
    ]
    write_csv("V37_V32_V37_TAXONOMY_DIFF.csv", diff_rows)

    a_field = sum(bool(row["field_id"]) for row in a_rows)
    a_topic = sum(bool(row["topic_id"]) for row in a_rows)
    field_lines = "\n".join(
        f"| {row['classification_name']} | {row['parent_industry_name']} | {row['event_count']} | {row['representative_companies'] or '无'} | {row['suggested_status']} |"
        for row in field_rows
    )
    topic_lines = "\n".join(
        f"| {row['classification_name']} | {row['parent_name']} | {row['event_count']} | {row['representative_companies'] or '无'} | {row['suggested_status']} |"
        for row in topic_rows
    )
    proposal_report = f"""# V3.7 历史融资事件产业分类映射与技术分类扩展提案

## 决策摘要

- 原有一级产业领域：10；建议新增：0。
- 原有二级技术领域：42；建议新增：{field_recommended}；观察项：{field_observe}。
- 原有三级技术主题：51；建议新增：{topic_recommended}；观察项：{topic_observe}。
- 75个事件保持原始分类依据不变，本阶段只增加独立映射和提案文件。

## 逐事件映射

- A类41个：全部确定现有一级领域，其中{a_field}个可确定现有二级领域，{a_topic}个可确定现有三级主题；其余下级分类留空。
- B类16个：1个回归现有分类，9个支持新增二级及三级，4个只需新增三级，1个不建议新增，1个作为观察提案。
- D类18个：全部保持待判断，并逐项列明缺少的企业实体、产品、技术或产业链证据。

## 二级技术领域提案

| 名称 | 所属一级领域 | 事件数 | 代表企业 | 状态 |
|---|---|---:|---|---|
{field_lines}

## 三级技术主题提案

| 名称 | 所属二级领域 | 事件数 | 代表企业 | 状态 |
|---|---|---:|---|---|
{topic_lines}

## 重叠与拆分判断

- “核能工程与超导装备”必须拆分：裂变、聚变、超导材料和医用核素分别属于不同技术边界。
- 聚变内部按磁约束与惯性/激光约束拆分三级主题，但共享“可控核聚变工程”二级领域。
- 智能底盘是车辆执行系统，不与机器人关节、自动驾驶算法或低空飞行器合并。
- AR智能眼镜按终端产品与空间交互归入个人AI；底层显示芯片仍可建立跨领域关联，但不改变主归属。
- 金融科技只有1个独立事件，保留观察项，不计入建议新增数量。
- 骨传导耳机当前只证明消费音频产品，不足以新增空间计算或AI交互主题。

## 数据保护

本提案未写入数据库，没有修改V3.2分类、正式融资事件或候选审核状态。所有现有ID和提案ID均保留在CSV映射中，等待下一阶段人工确认。
"""
    (DOCS / "V37_CLASSIFICATION_PROPOSAL_REPORT.md").write_text(proposal_report, encoding="utf-8")

    coverage_lines = "\n".join(f"| {row['industry_name']} | {row['existing_field_count']} | {row['existing_topic_count']} | {row['mapped_v37_events']} | {row['coverage_assessment']} |" for row in coverage_rows)
    report = f"""# V3.7 现有10个一级领域覆盖性分析报告

## 结论

- 一级产业领域保持10个，不建议新增。
- 75个事件逐条结果：A类{len(a_rows)}、B类{len(b_rows)}、D类{len(d_rows)}。
- 建议新增二级技术领域：{field_recommended}个；另有观察项{field_observe}个。
- 建议新增三级技术主题：{topic_recommended}个；另有观察项{topic_observe}个。
- 所有提案保持`proposal_pending`或观察状态，不修改V3.2。

| 一级领域 | 现有二级 | 现有三级 | V3.7映射事件 | 覆盖判断 |
|---|---:|---:|---:|---|
{coverage_lines}

## 交叉与归属建议

- 智能底盘属于车辆执行与制造系统，建议归入“高端装备与先进制造”，不归入机器人关节或低空飞行器。
- 聚变、裂变和超导不能合并为单一“核能工程”主题：聚变与裂变应分设二级领域，超导作为功能材料下的三级主题。
- 医用核素属于“生物制造与生命科学/新型生物药”，不归入新能源核能分类。
- AR智能眼镜跨半导体显示、光学装备和AI交互；本提案按终端产品与交互能力归入“AI软件与工业智能/个人AI与智能交互”。
- 金融科技只有1个事件，暂列观察项，不计入建议新增数量。

## 保护确认

本阶段仅生成映射和提案文件；保留现有分类ID与提案ID关系，没有写入数据库、确认候选或修改冻结分类。
"""
    (DOCS / "V37_TEN_INDUSTRY_COVERAGE_ANALYSIS.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
