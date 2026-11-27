from __future__ import annotations

import hashlib
import json
import uuid

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


NAMESPACE = uuid.UUID("1ad319df-a786-5df5-bae5-49e6d270c447")
BATCH_ID = str(uuid.uuid5(NAMESPACE, "2026-11-26_2026-11-27_increment"))


def source(article: int, title: str, excerpt: str) -> dict:
    return {
        "name": "投资界",
        "title": title,
        "url": f"https://news.pedaily.cn/202611/{article}.shtml",
        "excerpt": excerpt,
    }


def event(company: str, day: str, round_name: str, bucket: str, amount: str,
          investors: str, business: str, technology: str, evidence: dict,
          industry: str, *, suffix: str = "", status: str = "pending",
          currency: str | None = "CNY") -> dict:
    stable_id = str(uuid.uuid5(NAMESPACE, f"{company}|{day}|{round_name}|{suffix}"))
    return {
        "stable_id": stable_id, "company": company, "day": day,
        "round": round_name, "bucket": bucket, "amount": amount,
        "currency": currency, "investors": investors, "business": business,
        "technology": technology, "source": evidence, "industry": industry,
        "status": status,
    }


EVENTS = []

src = source(572486, "英汉思动力完成B轮融资，获国科投资超亿元投资",
             "英汉思动力完成超亿元人民币B轮融资，投资方为国科投资；资金用于机器人核心技术研发、产能扩容和海外渠道建设。")
EVENTS.append(event("英汉思动力", "2026-11-27", "B轮", "vc", "超亿元人民币", "国科投资",
                    "智能体育机器人及训练系统", "QDD电机、多模态感知、运动控制算法与体育物理AI模型",
                    src, "机器人与具身智能"))

src = source(572484, "博登智能完成数亿元B轮融资，以评测验证驱动人工智能数据生产",
             "博登智能完成数亿元B轮融资，多家机构共同参与；资金用于具身智能评测、全模态采集及数据生产平台升级。")
EVENTS.append(event("博登智能", "2026-11-27", "B轮", "vc", "数亿元人民币",
                    "金雨茂物、甬元基金、粤科创投、招商致远资本、招证投资、宁波高新区科创基金",
                    "Physical AI数据与评测基础设施", "全模态数据采集、机器人评测验证及采标训推平台",
                    src, "AI软件与工业智能"))

src = source(572483, "零次方新一轮融资启示：大模型无法击穿的，才是具身智能真正壁垒",
             "零次方机器人完成数亿元新一轮融资，报道未披露具体轮次；资金支持具身模型、真实场景履约与机器人产品落地。")
EVENTS.append(event("零次方机器人", "2026-11-27", "轮次未披露", "pending", "数亿元人民币",
                    "清科产投、锡洲国际、卓源亚洲、粤民溯锋、无锡滨湖、合肥建投、合肥产投国正、杰克集团等；同创伟业、力合基金、接力天使追加",
                    "具身机器人及零售仓储解决方案", "Zerith具身模型、ESI自进化框架与Picking泛化操作",
                    src, "机器人与具身智能", status="needs_verification"))

src = source(572482, "粒影生物完成过亿元A+轮融资，为AI4S模型量身定制私有数据库",
             "粒影生物完成过亿元A+轮融资，由皓禾资本领投；用于AI与真实世界实验闭环和生物数据基础设施建设。")
EVENTS.append(event("粒影生物", "2026-11-27", "A+轮", "vc", "过亿元人民币",
                    "皓禾资本（领投）；光明科学城产业发展集团、南京大健康基金及老股东（跟投）",
                    "AI4S生物数据生产与药物研发服务", "CFPS无细胞蛋白合成、高通量自动化与生物私有数据库",
                    src, "生物制造与生命科学"))

src = source(572480, "时空智子完成数千万元B轮融资，加速全链路闭环世界模型落地",
             "时空智子完成数千万元B轮融资，由光谷科创投、光谷人才基金及同创伟业联合投资。")
EVENTS.append(event("时空智子", "2026-11-27", "B轮", "vc", "数千万元人民币",
                    "光谷科创投、光谷人才基金、同创伟业",
                    "时空基础模型与行业智能体", "全链路闭环时空世界模型及Geosophon+平台",
                    src, "AI软件与工业智能"))

src = source(572475, "首发| 向量奇点完成数亿元A轮融资，阿里投了第一家量子公司",
             "向量奇点完成数亿元A轮融资，多家产业基金和市场化机构共同参与，用于中性原子量子计算产业化。")
EVENTS.append(event("向量奇点", "2026-11-27", "A轮", "vc", "数亿元人民币",
                    "北京市人工智能产业投资基金、北京北工及未来量子基金、中小企业发展促进基金、中关村科学城基金、招商局创投、阿里集团、啟赋资本、湖南财信、北洋海棠基金、雅瑞资本",
                    "中性原子量子计算软硬件", "中性原子量子计算机、量子比特操控与自动化实验智能体",
                    src, "量子科技"))

src = source(572454, "环码生物完成数千万美元A+轮融资，专注环形RNA疗法开发",
             "环码生物完成数千万美元A+轮融资，由复健资本领投，老股东持续加持。")
EVENTS.append(event("环码生物", "2026-11-26", "A+轮", "vc", "数千万美元",
                    "复健资本（领投）；老股东持续加持", "环形RNA创新药研发",
                    "环形RNA分子设计、递送与疗法开发", src, "生物制造与生命科学", currency="USD"))

src = source(572444, "迈塔兰斯完成超亿元A++轮融资，锚定光通信与光计算新赛道",
             "迈塔兰斯完成超亿元A++轮融资，多家中国机构投资；公司研发超表面光通信与光计算芯片。")
EVENTS.append(event("迈塔兰斯", "2026-11-26", "A++轮", "vc", "超亿元人民币",
                    "谷雨嘉禾、深圳知真投资、汇芯投资、江苏金桥基金、宁创投",
                    "超表面光通信与光计算芯片", "超表面器件、空间衍射光计算与视频生成光芯片",
                    src, "AI计算与半导体"))

src = source(572442, "华辰芯光完成pre-B++融资，年内已融三轮",
             "华辰芯光完成Pre-B++轮融资，用于FAB制造能力及高端光芯片规模化交付体系建设；金额和投资方未披露。")
EVENTS.append(event("华辰芯光", "2026-11-26", "Pre-B++轮", "vc", "未披露", "未披露",
                    "高端光通信芯片研发制造", "IDM光芯片、FAB制造与规模化交付",
                    src, "AI计算与半导体", status="needs_verification", currency=None))

src = source(572441, "华源智因获超亿元天使轮融资，AIVC在临床管线首个商业化订单落地",
             "华源智因完成超亿元天使轮融资，由华盖资本领投；公司以人体细胞药物响应世界模型服务药物研发。")
EVENTS.append(event("华源智因", "2026-11-26", "天使轮", "early", "超亿元人民币",
                    "华盖资本（领投）；华方资本、华映资本、梅花创投及中珠医疗、同新基金、讯飞创投、启赋资本（跟投）",
                    "AI虚拟细胞与药物研发服务", "多组学同细胞数据、人体细胞药物响应世界模型与临床药效预测",
                    src, "生物制造与生命科学"))

src = source(572436, "HearWell完成两轮数千万元融资，布局AI声学感知",
             "HearWell完成两轮融资，累计数千万元，报道未披露具体轮次；用于AI声学算法、智能硬件及商业化建设。")
EVENTS.append(event("HearWell", "2026-11-26", "两轮融资（轮次未披露）", "pending", "两轮累计数千万元人民币",
                    "博裕创投、璀璨资本、梅花创投、修远资本",
                    "AI声学感知及智能音频硬件", "实时场景感知、选择性倾听与声音理解算法",
                    src, "AI软件与工业智能", status="needs_verification"))

src = source(572420, "闪科光联连续完成两轮融资，聚焦AI算力「最后一米」光互连新赛道",
             "闪科光联连续完成种子轮和天使轮融资，累计数千万元，用于MicroLED光互连芯片研发和封装样品线建设。")
for round_name, investors, suffix in (
    ("种子轮", "励石创投（独家投资）", "seed"),
    ("天使轮", "商汤国香、长石资本、厚雪资本（联合领投）；险峰长青、磐霖资本、小苗朗程、柯熙创投等（跟投）", "angel"),
):
    EVENTS.append(event("闪科光联", "2026-11-26", round_name, "early", "两轮累计数千万元人民币（未拆分）",
                        investors, "MicroLED高速光互连芯片与光引擎",
                        "MicroLED、ALC/NPO/CPO短距光互连与先进封装", src,
                        "AI计算与半导体", suffix=suffix, status="needs_verification"))


RAW_RESULTS = (
    (572486, "2026-11-27", "英汉思动力完成B轮融资，获国科投资超亿元投资", "candidate", "B轮；中国科技企业"),
    (572484, "2026-11-27", "博登智能完成数亿元B轮融资，以评测验证驱动人工智能数据生产", "candidate", "B轮；中国科技企业"),
    (572483, "2026-11-27", "零次方新一轮融资启示：大模型无法击穿的，才是具身智能真正壁垒", "needs_verification", "已完成新一轮融资，具体轮次未披露"),
    (572482, "2026-11-27", "粒影生物完成过亿元A+轮融资，为AI4S模型量身定制私有数据库", "candidate", "A+轮；中国科技企业"),
    (572481, "2026-11-27", "柯君医药完成数亿元C+轮融资交割，加速推进心脑血管与代谢领域管线临床开发", "excluded", "C+轮超出目标轮次"),
    (572480, "2026-11-27", "时空智子完成数千万元B轮融资，加速全链路闭环世界模型落地", "candidate", "B轮；中国科技企业"),
    (572475, "2026-11-27", "首发| 向量奇点完成数亿元A轮融资，阿里投了第一家量子公司", "candidate", "A轮；中国科技企业"),
    (572454, "2026-11-26", "环码生物完成数千万美元A+轮融资，专注环形RNA疗法开发", "candidate", "A+轮；中国科技企业"),
    (572444, "2026-11-26", "迈塔兰斯完成超亿元A++轮融资，锚定光通信与光计算新赛道", "candidate", "A++轮；正文公司为中国企业，提及美国公司仅为技术路线比较"),
    (572442, "2026-11-26", "华辰芯光完成pre-B++融资，年内已融三轮", "candidate", "Pre-B++轮；中国科技企业"),
    (572441, "2026-11-26", "华源智因获超亿元天使轮融资，AIVC在临床管线首个商业化订单落地", "candidate", "天使轮；中国科技企业"),
    (572436, "2026-11-26", "HearWell完成两轮数千万元融资，布局AI声学感知", "needs_verification", "两轮融资均未披露具体轮次"),
    (572420, "2026-11-26", "闪科光联连续完成两轮融资，聚焦AI算力「最后一米」光互连新赛道", "candidate", "正文明确种子轮和天使轮"),
)


def import_increment() -> dict[str, int]:
    migrate()
    timestamp = now()
    with connect() as connection, connection:
        industry_ids = {row["name"]: row["industry_id"] for row in connection.execute(
            "SELECT industry_id,name FROM v30_industries WHERE taxonomy_version='V3.2'"
        )}
        connection.execute(
            """INSERT INTO v35_collection_batches
               (batch_id,batch_name,period_start,period_end,scope_note,status,source_count,raw_source_count,
                new_candidate_count,duplicate_source_count,effective_event_count,vc_event_count,early_event_count,
                pending_round_count,pending_classification_count,started_at,completed_at,created_by,created_at,updated_at)
               VALUES (?,?,?,?,?,'completed',1,13,13,1,12,8,3,2,0,?,?,?,?,?)
               ON CONFLICT(batch_id) DO UPDATE SET status='completed',source_count=1,raw_source_count=13,
                 new_candidate_count=13,duplicate_source_count=1,effective_event_count=12,vc_event_count=8,
                 early_event_count=3,pending_round_count=2,pending_classification_count=0,
                 completed_at=excluded.completed_at,updated_at=excluded.updated_at""",
            (BATCH_ID, "2026年11月26日至27日融资增量", "2026-11-26", "2026-11-27",
             "中国科技全领域；VC成长轮、种子/天使轮及轮次待核验；投资界逐篇正文核验。",
             timestamp, timestamp, "codex_v35_daily_increment", timestamp, timestamp),
        )
        connection.execute("DELETE FROM v35_collection_searches WHERE batch_id=?", (BATCH_ID,))
        connection.execute("DELETE FROM v35_collection_search_results WHERE batch_id=?", (BATCH_ID,))
        for day, count in (("2026-11-26", 6), ("2026-11-27", 7)):
            connection.execute(
                "INSERT INTO v35_collection_searches VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uid(), BATCH_ID, day, "投资界", "融资频道逐日归档及正文逐篇核验", count,
                 count - (1 if day == "2026-11-27" else 0), "completed", "正文逐条核验", timestamp),
            )
        for article, day, title, status, reason in RAW_RESULTS:
            url = f"https://news.pedaily.cn/202611/{article}.shtml"
            connection.execute(
                "INSERT INTO v35_collection_search_results VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid5(NAMESPACE, "result|" + url)), BATCH_ID, "投资界", title, url,
                 day, status, reason, timestamp),
            )
        for row in EVENTS:
            candidate_id = str(uuid.uuid5(NAMESPACE, "candidate|" + row["stable_id"]))
            connection.execute(
                """INSERT OR IGNORE INTO v35_historical_candidates
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (candidate_id, BATCH_ID, row["stable_id"], row["company"], row["day"], None,
                 row["round"], row["bucket"], row["amount"], row["currency"], row["investors"],
                 row["business"], row["technology"], "B", row["status"],
                 "codex_v35_daily_increment", timestamp, timestamp),
            )
            evidence = row["source"]
            digest = hashlib.sha256((evidence["title"] + "\n" + evidence["excerpt"]).encode()).hexdigest()
            connection.execute(
                """INSERT OR IGNORE INTO v35_candidate_sources VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid5(NAMESPACE, candidate_id + "|" + evidence["url"])), candidate_id,
                 evidence["name"], evidence["title"], evidence["url"], row["day"], evidence["excerpt"],
                 1, "accessible", digest, timestamp),
            )
            connection.execute(
                """INSERT OR IGNORE INTO v35_classification_proposals
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (str(uuid.uuid5(NAMESPACE, "proposal|" + candidate_id)), candidate_id, "existing_taxonomy",
                 None, None, None, industry_ids[row["industry"]], None, None,
                 row["technology"], "沿用V3.2冻结一级产业；不修改冻结分类体系。",
                 "企业业务和核心技术可直接匹配现有一级产业。", 1, 1, "pending",
                 "codex_v35_daily_increment", timestamp),
            )
        audit_summary = json.dumps({"raw_articles": 13, "candidate_sources": 12,
                                    "candidate_rows": 13, "display_events": 12, "excluded": 1},
                                   ensure_ascii=False)
        existing_audit = connection.execute(
            "SELECT 1 FROM audit_logs WHERE action='import_v35_nov26_27' AND entity_id=?", (BATCH_ID,)
        ).fetchone()
        if existing_audit:
            connection.execute(
                "UPDATE audit_logs SET after_json=? WHERE action='import_v35_nov26_27' AND entity_id=?",
                (audit_summary, BATCH_ID),
            )
        else:
            connection.execute(
                "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uid(), "codex_v35_daily_increment", "import_v35_nov26_27", "v35_collection_batch",
                 BATCH_ID, None, audit_summary,
                 "Two-day verified increment; candidate and proposal layers only.", None, timestamp),
            )
    return {"raw_articles": len(RAW_RESULTS), "candidate_rows": len(EVENTS), "display_events": 12}


if __name__ == "__main__":
    print(json.dumps(import_increment(), ensure_ascii=False))
