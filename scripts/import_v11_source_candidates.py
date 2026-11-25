from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
PEDAILY = ROOT / "work" / "pedaily_v11_crawl.json"
SPACEDAILY = ROOT / "work" / "spacedaily_v11_audit.json"
SPACEDAILY_ORIGINALS = ROOT / "work" / "spacedaily_originals_v11.json"
NS = uuid.UUID("c35e9d9a-51f8-44e7-84f4-292fdce851ca")
ROUND_RE = re.compile(r"(B\+\+轮|B\+轮|B轮|Pre[-－]?B\+?轮|A\+\+轮|A\+轮|A轮|Pre[-－]?A\+?轮|天使\+?轮|种子轮|战略轮|战略融资)", re.I)
TECH_RE = re.compile(r"AI|人工智能|机器人|具身|芯片|半导体|算力|光子|量子|材料|能源|电池|储能|制造|工业|软件|航空|航天|卫星|生物|医疗|医药|基因|细胞|蛋白|检测|传感|激光|光学|通信|电源|无人机|智能|科技|数据|云|安全|封装|涂料|装备|器械|质谱|电子", re.I)


def sid(value: str) -> str:
    return str(uuid.uuid5(NS, value))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def company_name(title: str) -> str:
    value = re.sub(r"^首发\s*[|｜:]\s*", "", title).strip()
    value = value.replace("「", "").replace("」", "")
    patterns = [r"完成", r"连续完成", r"获(?:得)?", r"B\+?轮", r"A\+?轮", r"Pre[-－]?A", r"天使轮", r"种子轮"]
    positions = [m.start() for p in patterns if (m := re.search(p, value, re.I))]
    value = value[: min(positions)] if positions else value.split("，", 1)[0]
    value = re.sub(r"^(?:AI原生芯片设计公司|原生AGI架构芯片研发商|RDMA智能网卡芯片设计领军厂商|eVTOL交易与运力服务商|AI智能体基础设施公司)", "", value)
    return value.strip(" ：:（）()\"' ")[:120]


def round_fields(title: str) -> tuple[str, str]:
    matches = ROUND_RE.findall(title)
    original = "、".join(dict.fromkeys(matches)) if matches else "轮次待核验"
    normalized = original.replace("－", "-")
    if "战略" in normalized:
        normalized = "战略融资"
    elif "种子" in normalized:
        normalized = "Seed"
    elif "天使+" in normalized:
        normalized = "Angel+"
    elif "天使" in normalized:
        normalized = "Angel"
    return original, normalized


def amount(title: str) -> str:
    match = re.search(r"((?:约|近|超|逾|数)?(?:\d+(?:\.\d+)?|[一二三四五六七八九十两]+)?(?:百|千|万|亿)?(?:美元|欧元|人民币|元)(?:级|以上|规模)?)", title)
    return match.group(1) if match else "未披露"


def main() -> None:
    pedaily = json.loads(PEDAILY.read_text(encoding="utf-8"))
    spacedaily = json.loads(SPACEDAILY.read_text(encoding="utf-8"))
    spacedaily_originals = json.loads(SPACEDAILY_ORIGINALS.read_text(encoding="utf-8"))
    con = sqlite3.connect(database_path())
    con.row_factory = sqlite3.Row
    timestamp = now()
    with con:
        con.execute("DELETE FROM source_event_observations WHERE source_name IN ('投资界','SpaceDaily融资数据库')")
        con.execute("DELETE FROM v11_funding_candidates")
        con.execute("DELETE FROM source_document_audit WHERE discovery_channel IN ('投资界公开分页','SpaceDaily公开HTML')")
        con.execute("DELETE FROM source_audit_pages WHERE run_id IN (SELECT run_id FROM source_audit_runs WHERE source_name='投资界')")
        con.execute("DELETE FROM source_audit_runs WHERE source_name='投资界'")
        con.execute("INSERT OR IGNORE INTO sources (source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("source-pedaily-v11", "投资界", "professional_media", "media", "B", "https://www.pedaily.cn/", "robots_allow", timestamp))
        con.execute("INSERT OR IGNORE INTO sources (source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("source-spacedaily-v11", "SpaceDaily融资数据库", "aggregator", "database", "C", "https://fund.spacedaily.com.cn/", "robots_allow_public_only", timestamp))
        con.execute("INSERT OR IGNORE INTO sources (source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at) VALUES (?,?,?,?,?,?,?,?)", ("source-other-public-v11", "其他公开融资来源", "professional_media", "media", "C", None, "public_pages_only", timestamp))
        for column in {p["column"] for p in pedaily["pages"]}:
            run_id = sid("pedaily-run:" + column)
            con.execute("INSERT OR IGNORE INTO source_audit_runs VALUES (?,?,?,?,?,?,?,?)", (run_id, "投资界", column, pedaily["generated_at"], pedaily["generated_at"], "allow:/", "public_html_low_frequency", "连续两页早于窗口或无文章后停止"))
        for page in pedaily["pages"]:
            run_id = sid("pedaily-run:" + page["column"])
            con.execute("INSERT OR IGNORE INTO source_audit_pages VALUES (?,?,?,?,?,?,?,?,?,?)", (
                sid("pedaily-page:" + page["url"]), run_id, page["page"], page["url"], page.get("http_status"), page["article_count"], page.get("newest_date") or None, page.get("oldest_date") or None,
                "accessible" if page.get("http_status") == 200 else "failed", pedaily["generated_at"],
            ))
        existing_docs = {r["original_url"]: r for r in con.execute("SELECT document_id,original_url FROM raw_documents")}
        companies = [dict(r) for r in con.execute("SELECT company_id,official_name,short_name FROM companies")]
        existing_events = [dict(r) for r in con.execute("SELECT event_id,company_id,announcement_date,round_original FROM funding_events")]
        company_by_id = {x["company_id"]: x for x in companies}
        candidate_by_url: dict[str, str] = {}
        for article in pedaily["articles"]:
            url = article["url"]
            document_id = existing_docs[url]["document_id"] if url in existing_docs else sid("document:" + url)
            if url not in existing_docs:
                content = article.get("page_text", "")
                con.execute("INSERT INTO raw_documents (document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,discovered_via_document_id,archive_status,parser_version,relevance_status,review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    document_id, "source-pedaily-v11", url, url, article["title"], article["published_date"], pedaily["generated_at"], content,
                    hashlib.sha256(content.encode()).hexdigest(), "media", None, "text_saved" if article.get("accessible") else "metadata_only", "pedaily-v11", "pending", "parsed", timestamp,
                ))
            columns = ",".join(article["columns"])
            con.execute("INSERT OR IGNORE INTO source_document_audit VALUES (?,?,?,?,?,?,?,?,?,?)", (
                document_id, columns, "accessible", "accessible" if article.get("accessible") else "failed", "B", 0, None, "投资界公开分页", "", pedaily["generated_at"],
            ))
            if not ROUND_RE.search(article["title"]) or not TECH_RE.search(article["title"]):
                continue
            name = company_name(article["title"])
            ro, rn = round_fields(article["title"])
            duplicate_event = None
            for event in existing_events:
                company = company_by_id[event["company_id"]]
                names = (company["official_name"], company.get("short_name") or "")
                if any(name and (name in n or n in name) for n in names if n) and abs((datetime.fromisoformat(article["published_date"]) - datetime.fromisoformat(event["announcement_date"])).days) <= 3:
                    duplicate_event = event["event_id"]
                    break
            if url in existing_docs:
                linked = con.execute("SELECT event_id FROM event_documents WHERE document_id=? LIMIT 1", (document_id,)).fetchone()
                duplicate_event = linked[0] if linked else duplicate_event
            status = "duplicate_v1" if duplicate_event else "verified_new"
            candidate_id = sid("funding-candidate:" + url)
            candidate_by_url[url] = candidate_id
            con.execute("INSERT OR IGNORE INTO v11_funding_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                candidate_id, name, article["published_date"], ro, rn, amount(article["title"]), document_id, status, duplicate_event, None, "B",
                "投资界正文可访问，标题及正文明确披露目标轮次融资" if not duplicate_event else "与V1.0企业、日期、轮次或原始URL匹配",
                "企业法定名称、融资实际交割日期及部分投资方仍需人工复核", timestamp,
            ))
            con.execute("INSERT OR IGNORE INTO source_event_observations VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                sid("obs:pedaily:" + url), "投资界", columns, url, document_id, candidate_id, duplicate_event, 1 if duplicate_event else 0, "verified", "正文可访问", timestamp,
            ))
        for record in spacedaily["target_records"]:
            url = record.get("su") or f"spacedaily-record:{record['id']}"
            candidate_id = candidate_by_url.get(url)
            con.execute("INSERT OR IGNORE INTO source_event_observations VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                sid("obs:spacedaily:" + str(record["id"])), "SpaceDaily融资数据库", record.get("s") or "未分类", str(record["id"]), None, candidate_id, None,
                1 if candidate_id else 0, "pending", "公开HTML记录；企业、地区、日期、轮次、金额和投资方均需回到原始链接复核", timestamp,
            ))
        record_by_id = {x["id"]: x for x in spacedaily["target_records"]}
        for original in spacedaily_originals["records"]:
            url = original["url"]
            first = record_by_id[original["record_ids"][0]]
            existing = con.execute("SELECT document_id FROM raw_documents WHERE original_url=? LIMIT 1", (url,)).fetchone()
            document_id = existing[0] if existing else sid("document:" + url)
            if not existing:
                content = original.get("text", "")
                con.execute("INSERT INTO raw_documents (document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,discovered_via_document_id,archive_status,parser_version,relevance_status,review_status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    document_id, "source-other-public-v11", url, original.get("final_url") or url, first.get("st") or first.get("c") or url,
                    first.get("d"), spacedaily_originals["generated_at"], content, hashlib.sha256(content.encode()).hexdigest(), "media", None,
                    "text_saved" if original.get("accessible") else "metadata_only", "spacedaily-original-v11", "uncertain", "discovered", timestamp,
                ))
            con.execute("INSERT OR IGNORE INTO source_document_audit VALUES (?,?,?,?,?,?,?,?,?,?)", (
                document_id, first.get("s") or "未分类", "accessible", "accessible" if original.get("accessible") else "failed", "C", 1 if url in candidate_by_url else 0, None,
                "SpaceDaily公开HTML", "聚合器发现；需独立核验企业、地区、日期、轮次和金额", spacedaily_originals["generated_at"],
            ))
            for record_id in original["record_ids"]:
                con.execute("UPDATE source_event_observations SET document_id=? WHERE source_name='SpaceDaily融资数据库' AND external_key=?", (document_id, str(record_id)))
    stats = {
        "pedaily_documents": con.execute("SELECT count(*) FROM source_document_audit WHERE discovery_channel='投资界公开分页'").fetchone()[0],
        "funding_candidates": con.execute("SELECT count(*) FROM v11_funding_candidates").fetchone()[0],
        "duplicates_v1": con.execute("SELECT count(*) FROM v11_funding_candidates WHERE candidate_status='duplicate_v1'").fetchone()[0],
        "verified_new": con.execute("SELECT count(*) FROM v11_funding_candidates WHERE candidate_status='verified_new'").fetchone()[0],
        "spacedaily_observations": con.execute("SELECT count(*) FROM source_event_observations WHERE source_name='SpaceDaily融资数据库'").fetchone()[0],
        "spacedaily_original_documents": con.execute("SELECT count(*) FROM source_document_audit WHERE discovery_channel='SpaceDaily公开HTML'").fetchone()[0],
    }
    con.close()
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
