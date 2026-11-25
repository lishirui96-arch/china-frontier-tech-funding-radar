from __future__ import annotations

import csv
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from funding_radar.amounts import parse_amount
from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now

CANDIDATES = ROOT / "docs" / "NOVEMBER_2026_FUNDING_CANDIDATES.csv"
SOURCES = ROOT / "docs" / "NOVEMBER_2026_SOURCE_REGISTER.csv"
NAMESPACE = uuid.UUID("5cfe7a3d-f6b1-4d26-b96f-2b2515b889c1")

EXCLUDED = {
    "CNF-202611-002": "轮次未披露，不能确认属于早期融资范围",
    "CNF-202611-004": "轮次未披露，不能确认属于早期融资范围",
    "CNF-202611-018": "D轮超出本阶段早期融资范围",
}

CONFIG = {
    "CNF-202611-001": ("other_emerging","生成式视频基础模型","A+","early_financing"),
    "CNF-202611-003": ("biomanufacturing","虚拟细胞与AI for Science","Pre-A","early_financing"),
    "CNF-202611-005": ("ai_chips_manufacturing","半导体热管理材料","B+","early_financing"),
    "CNF-202611-006": ("other_emerging","高端医疗器械","B","early_financing"),
    "CNF-202611-007": ("ai_chips_manufacturing","先进封装玻璃基板装备","Angel","early_financing"),
    "CNF-202611-008": ("robotics","脑机接口与柔性传感","Angel+","early_financing"),
    "CNF-202611-009": ("energy_materials","高空风力发电","Angel","early_financing"),
    "CNF-202611-010": ("quantum_computing","超导量子计算","Angel","early_financing"),
    "CNF-202611-011": ("robotics","具身智能机器人","Pre-A","early_financing"),
    "CNF-202611-012": ("quantum_computing","区块链安全与监管科技","Strategic Equity","strategic_equity"),
    "CNF-202611-013": ("ai_chips_manufacturing","Micro-LED驱动芯片","B","early_financing"),
    "CNF-202611-014": ("other_emerging","商业航天与卫星遥感","A+","early_financing"),
    "CNF-202611-015": ("ai_chips_manufacturing","EUV光源","Pre-A","early_financing"),
    "CNF-202611-016": ("ai_chips_manufacturing","AI算力光互连","Pre-A","early_financing"),
    "CNF-202611-017": ("ai_chips_manufacturing","先进封装无损检测","Pre-A","early_financing"),
    "CNF-202611-019": ("robotics","空中具身智能","Pre-B","early_financing"),
    "CNF-202611-020": ("biomanufacturing","器官芯片与3D生物智能","Strategic Equity","strategic_equity"),
    "CNF-202611-021": ("ai_chips_manufacturing","功率半导体封装材料","A","early_financing"),
    "CNF-202611-022": ("ai_chips_manufacturing","半导体与光通信视觉检测","B+","early_financing"),
    "CNF-202611-023": ("ai_chips_manufacturing","工业仿真软件与工业AI","A+","early_financing"),
    "CNF-202611-024": ("energy_materials","核聚变电源与电力电子AI","Strategic Equity","strategic_equity"),
    "CNF-202611-025": ("ai_chips_manufacturing","晶圆键合设备","B","early_financing"),
}

THEMES = {
    "TH-001": ("AI for Science干湿实验基础设施", "biomanufacturing", "研发基础设施", ["CNF-202611-003","CNF-202611-020"]),
    "TH-002": ("先进封装材料、装备与检测", "ai_chips_manufacturing", "材料/装备/检测", ["CNF-202611-005","CNF-202611-007","CNF-202611-017","CNF-202611-021","CNF-202611-022","CNF-202611-025"]),
    "TH-003": ("具身机器人感知、执行与本体", "robotics", "核心器件与系统", ["CNF-202611-008","CNF-202611-011","CNF-202611-019"]),
    "TH-004": ("AI算力光互连与显示驱动", "ai_chips_manufacturing", "芯片与互连", ["CNF-202611-013","CNF-202611-015","CNF-202611-016"]),
    "TH-005": ("工业仿真与电力电子开发工具", "other_emerging", "工业软件", ["CNF-202611-023","CNF-202611-024"]),
    "TH-006": ("生成式视频基础模型观察项", "other_emerging", "基础模型", ["CNF-202611-001"]),
    "TH-007": ("高空风力发电观察项", "energy_materials", "发电装备", ["CNF-202611-009"]),
    "TH-008": ("超导量子计算观察项", "quantum_computing", "计算硬件", ["CNF-202611-010"]),
    "TH-009": ("卫星遥感数智服务观察项", "other_emerging", "下游应用", ["CNF-202611-014"]),
    "TH-010": ("区块链安全与监管科技观察项", "quantum_computing", "安全软件", ["CNF-202611-012"]),
    "TH-011": ("高端电外科平台观察项", "other_emerging", "医疗器械", ["CNF-202611-006"]),
}


def stable(kind: str, value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{value}"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    migrate()
    candidates = load_csv(CANDIDATES)
    source_rows = load_csv(SOURCES)
    source_by_url = {row["原始URL"]: row for row in source_rows}
    t = now()
    connection = connect()
    try:
        with connection:
            connection.execute("INSERT OR IGNORE INTO amount_rule_versions VALUES (?,?,?,?,?)", ("amount-v1","1.0.0",json.dumps({"parser":"funding_radar.amounts.parse_amount"},ensure_ascii=False),1,t))
            event_lookup: dict[str, tuple[str,str]] = {}
            keyword_lookup: dict[tuple[str,str], str] = {}
            for row in candidates:
                cid, url = row["候选事件ID"], row["原始融资报道URL"]
                source_meta = source_by_url.get(url, {})
                domain = urlsplit(url).netloc.lower()
                source_id = stable("source", domain)
                grade = row["来源等级"] if row["来源等级"] in {"S","A","B","C","D"} else "C"
                connection.execute("""INSERT OR IGNORE INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at,is_active,allowed_scope,min_interval_seconds,failure_count)
                  VALUES (?,?,?,?,?,?,?, ?,1,'metadata_and_evidence_excerpt',3600,0)""", (source_id,source_meta.get("来源名称") or domain,"professional_media","media",grade,f"https://{domain}","reviewed",t))
                document_id = stable("document", url)
                title = source_meta.get("线索标题") or row["企业名称"] + "融资报道"
                excerpt = row["证据说明"]
                connection.execute("""INSERT OR IGNORE INTO raw_documents(document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,archive_status,parser_version,relevance_status,review_status,created_at,source_domain,fetch_status,financing_category,event_link_status,imported_at)
                  VALUES (?,?,?,?,?,?,?,?,?,'media','summary_saved','november-v1','relevant','field_review',?,?,'success','primary_equity','linked',?)""",
                  (document_id,source_id,url,url,title,row["融资公布日期"],t,excerpt,stable("hash",excerpt),t,domain,t))
                if cid in EXCLUDED:
                    continue
                category, track, normalized_round, financing_type = CONFIG[cid]
                company_id = stable("company", row["企业名称"])
                connection.execute("""INSERT OR IGNORE INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (company_id,row["企业名称"],row["企业名称"],None,row["企业所在地"] or None,None,"legal_entity","needs_review","pending",document_id,t,t))
                parsed = parse_amount(row["融资金额原文"])
                event_id = stable("event", cid)
                status = "field_review"
                connection.execute("""INSERT OR IGNORE INTO funding_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (event_id,company_id,row["融资公布日期"],None,row["融资轮次"],normalized_round,row["融资金额原文"],parsed.exact,parsed.minimum,parsed.maximum,parsed.currency,parsed.disclosure_type,"amount-v1",parsed.confidence,int(parsed.cumulative),None,"candidate",grade,status,None,t,t))
                normalized_cny = parsed.exact if parsed.currency == "CNY" and not parsed.cumulative else None
                connection.execute("""INSERT OR IGNORE INTO sample_event_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (event_id,"2026-11",None,financing_type,normalized_round,category,track,row["所属技术方向"],normalized_cny,None,"2026-11-25","included","正文明确融资事实；证据仍待人工双审",t,t))
                connection.execute("INSERT OR IGNORE INTO event_documents VALUES (?,?, 'primary',1,?)", (event_id,document_id,t))
                for field, value in (("company_id",row["企业名称"]),("financing_fact",row["证据说明"]),("announcement_date",row["融资公布日期"]),("round_original",row["融资轮次"]),("amount_original",row["融资金额原文"])):
                    connection.execute("INSERT OR IGNORE INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,'pending',NULL,NULL,?)", (stable("evidence",f"{event_id}:{field}"),document_id,"funding_event",event_id,field,value,0,len(value),grade,t))
                for investor_name in [x.strip() for x in row["投资机构"].split("|") if x.strip() and x.strip() != "未披露"]:
                    official = investor_name.split("（",1)[0]
                    investor_id = stable("investor", official)
                    connection.execute("INSERT OR IGNORE INTO investors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (investor_id,official,official,None,None,None,"unknown","needs_review","pending",document_id,t,t))
                    role = "exclusive" if "独家" in investor_name else ("lead" if "领投" in investor_name else ("existing_additional" if "老股东" in investor_name else "follow"))
                    connection.execute("INSERT OR IGNORE INTO event_investors VALUES (?,?,?,?,?,?,?)", (stable("event-investor",f"{event_id}:{investor_id}:{role}"),event_id,investor_id,role,investor_name,None,t))
                profile_id = stable("profile", company_id)
                cross_tags = json.dumps([x for x in {row["所属技术方向"],track} if x],ensure_ascii=False)
                connection.execute("""INSERT OR IGNORE INTO company_technology_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (profile_id,company_id,row["核心产品"],row["核心产品"],row["核心技术"],"未单独披露",row["所属技术方向"],"未单独披露",None,category,track,cross_tags,"partially_verified","pending",t,t))
                connection.execute("INSERT OR IGNORE INTO technology_profile_sources VALUES (?,?,?,?,?)", (profile_id,document_id,json.dumps(["primary_business","core_products","core_technologies","secondary_track"],ensure_ascii=False),"partially_verified",t))
                keywords = [x.strip() for x in row["核心技术"].split("|") if x.strip()]
                for raw in keywords:
                    normalized = raw.replace("技术","").strip() or raw
                    key = (normalized,category)
                    keyword_id = keyword_lookup.setdefault(key,stable("keyword",f"{category}:{normalized}"))
                    connection.execute("INSERT OR IGNORE INTO technology_keywords VALUES (?,?,?,?,?,?,?)", (keyword_id,raw,normalized,f"来自{row['企业名称']}融资报道的原始技术表达",category,"partially_verified",t))
                    connection.execute("INSERT OR IGNORE INTO technology_keyword_links VALUES (?,?,?,?,?,?,?)", (keyword_id,company_id,event_id,document_id,"core","pending",t))
                event_lookup[cid] = (event_id,company_id)
            for theme_id,(description,category,position,members) in THEMES.items():
                tid = stable("theme",theme_id)
                connection.execute("""INSERT OR IGNORE INTO candidate_themes VALUES (?,?,?,?,?,?,?,'pending',NULL,0,NULL,?,?)""",
                  (tid,description,category,position,"由共同技术关键词、主营业务和产业链位置形成；不代表最终热点", "仅包含本批次有正文证据的企业；单企业方向保留为观察项", "是否存在足够跨企业技术同质性；是否应合并、拆分或暂缓",t,t))
                for cid in members:
                    if cid not in event_lookup: continue
                    event_id,company_id = event_lookup[cid]
                    connection.execute("INSERT OR IGNORE INTO candidate_theme_members VALUES (?,?,?,?,1,?)", (tid,company_id,event_id,"技术关键词与产业链位置相近，待人工审核",t))
                    for keyword_id, in connection.execute("SELECT keyword_id FROM technology_keyword_links WHERE event_id=?",(event_id,)).fetchall():
                        connection.execute("INSERT OR IGNORE INTO candidate_theme_keywords VALUES (?,?)",(tid,keyword_id))
    finally:
        connection.close()
    print(json.dumps({"candidate_sources":len(candidates),"included_events":len(CONFIG),"excluded":EXCLUDED,"themes":len(THEMES)},ensure_ascii=False))


if __name__ == "__main__":
    main()
