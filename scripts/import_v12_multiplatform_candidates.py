from __future__ import annotations

import email.utils
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "work" / "spacedaily_v11_audit.json"
ORIGINALS = ROOT / "work" / "spacedaily_originals_v11.json"
PLATFORMS = ROOT / "work" / "independent_platforms_v12.json"
NS = uuid.UUID("92d3f88f-0bd2-497c-bb15-ef6aef5bbb08")
ALLOWED = {"种子轮", "天使轮", "天使+轮", "Pre-A", "Pre-A+", "A轮", "A+轮", "A++轮", "Pre-B", "B轮", "B+轮", "B++轮"}
ROUND_RE = re.compile(r"(种子轮|天使\+?轮|Pre[-－]?A\+?轮?|A\+\+?轮|A轮|Pre[-－]?B\+?轮?|B\+\+?轮|B轮|战略融资)", re.I)
AMOUNT_RE = re.compile(r"((?:约|近|超|逾|数)?(?:\d+(?:\.\d+)?|[一二三四五六七八九十两]+)?(?:百|千|万|亿)?(?:美元|欧元|人民币|元)(?:级|以上|规模)?)")
FOREIGN = re.compile(r"OpenAI|Ramon\.Space|Qluster|Reflect Orbital|Mirendil|SE3|Linq|Embo|Sqwish|CataXAI|GenRobot|Rex Bionics", re.I)
WEEKLY = re.compile(r"周报|盘点|汇总")


def uid(value: str) -> str:
    return str(uuid.uuid5(NS, value))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value or "").lower()


def company_from_title(title: str) -> str:
    value = re.sub(r"^首发\s*[|｜:]\s*", "", title).strip().replace("「", "").replace("」", "").replace("“", "").replace("”", "")
    value = re.sub(r"^(?:AI原生芯片设计公司|原生AGI架构芯片研发商|RDMA智能网卡芯片设计领军厂商|eVTOL交易与运力服务商|具身大脑企业)", "", value)
    matches = [m.start() for p in (r"完成", r"宣布完成", r"获(?:得)?", r"B\+?轮", r"A\+?轮", r"Pre[-－]?A", r"天使轮", r"种子轮") if (m := re.search(p, value, re.I))]
    value = value[:min(matches)] if matches else value.split("，", 1)[0]
    return value.strip(" ：:（）()\"' ")[:160]


def normalized_round(value: str) -> str:
    value = (value or "").replace("－", "-").strip()
    mapping = {"种子轮": "Seed", "天使轮": "Angel", "天使+轮": "Angel+", "Pre-A": "Pre-A", "Pre-A轮": "Pre-A", "Pre-A+": "Pre-A+", "Pre-A+轮": "Pre-A+", "A轮": "A", "A+轮": "A+", "A++轮": "A++", "Pre-B": "Pre-B", "Pre-B轮": "Pre-B", "B轮": "B", "B+轮": "B+", "B++轮": "B++", "战略融资": "Strategic"}
    return mapping.get(value, value or "Unknown")


def round_from_title(title: str) -> tuple[str, str]:
    matches = list(dict.fromkeys(ROUND_RE.findall(title)))
    original = "、".join(matches) if matches else "轮次待核验"
    normalized = "、".join(normalized_round(x) for x in matches) if matches else "Unknown"
    return original, normalized


def dates_close(left: str, right: str, days: int = 3) -> bool:
    try:
        return abs((datetime.fromisoformat(left[:10]) - datetime.fromisoformat(right[:10])).days) <= days
    except Exception:
        return False


def same_company(left: str, right: str) -> bool:
    a, b = compact(left), compact(right)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 3 and (a in b or b in a))


def target_round_matches(left: str, right: str) -> bool:
    a, b = normalized_round(left), normalized_round(right)
    return a == b or a in b or b in a or (a.startswith("A") and b.startswith("A")) or (a.startswith("B") and b.startswith("B")) or (a.startswith("Angel") and b.startswith("Angel"))


def category(sector: str) -> tuple[str, str]:
    mapping = {"人工智能": "人工智能与AI基础设施", "具身智能": "机器人与具身智能", "半导体": "半导体与先进封装", "量子科技": "量子信息与先进计算", "新能源": "新能源与储能", "新材料": "新材料", "生物医药": "生物制造与生命科技", "高端装备": "高端制造", "低空经济": "商业航天与低空经济", "商业航天": "商业航天与低空经济"}
    return mapping.get(sector, "其他新兴技术方向"), sector or "待分类"


def main() -> None:
    space = json.loads(SPACE.read_text(encoding="utf-8"))
    originals = json.loads(ORIGINALS.read_text(encoding="utf-8"))
    platforms = json.loads(PLATFORMS.read_text(encoding="utf-8"))
    access_by_url = {x["url"]: x for x in originals["records"]}
    con = sqlite3.connect(database_path()); con.row_factory = sqlite3.Row
    timestamp = now()
    v11 = [dict(r) for r in con.execute("""SELECT c.*,d.title,d.original_url FROM v11_funding_candidates c
        JOIN raw_documents d ON d.document_id=c.source_document_id""")]
    formal = [dict(r) for r in con.execute("""SELECT e.event_id,e.announcement_date,e.round_original,c.official_name,c.short_name
        FROM funding_events e JOIN companies c USING(company_id)""")]

    def v11_match(name: str, date: str, round_value: str, title: str) -> dict | None:
        best, score = None, 0.0
        for row in v11:
            if not dates_close(date, row["disclosure_date"]):
                continue
            company_score = 1.0 if same_company(name, row["company_name_original"]) else 0.0
            title_score = SequenceMatcher(None, compact(title), compact(row["title"])).ratio()
            round_score = 0.25 if target_round_matches(round_value, row["round_original"]) else 0.0
            total = max(company_score, title_score) + round_score
            if total > score:
                best, score = row, total
        return best if score >= 0.85 else None

    def formal_match(name: str, date: str, round_value: str) -> dict | None:
        for row in formal:
            if dates_close(date,row["announcement_date"]) and target_round_matches(round_value,row["round_original"]) and (same_company(name,row["official_name"]) or same_company(name,row.get("short_name") or "")):
                return row
        return None

    with con:
        con.execute("DELETE FROM v12_candidate_source_links")
        con.execute("DELETE FROM v12_funding_candidates")
        con.execute("DELETE FROM v12_source_records")
        con.execute("DELETE FROM v12_platform_audits")
        con.execute("DELETE FROM v12_acquisition_candidates")
        space_candidates: list[dict] = []
        for record in space["november_records"]:
            url = record.get("su") or ""
            access = access_by_url.get(url, {})
            name = record.get("c") or ""
            match = v11_match(name, record.get("d") or "", record.get("r") or "", record.get("st") or "")
            formal_hit = formal_match(name,record.get("d") or "",record.get("r") or "")
            if record.get("co") != "中国" or FOREIGN.search(name):
                market, basis = "not_china", "网站标签或企业名称显示为境外主体；未作为中国样本"
            elif match:
                market, basis = "confirmed_china", "与投资界中国科技企业候选在企业、日期和轮次上匹配"
            elif re.search(r"[\u4e00-\u9fff]{2,}", name) and not re.search(r"公司\s+[A-Za-z]", name):
                market, basis = "probable_china", "中文企业名称且原始记录标记中国；法定注册主体仍待官方来源确认"
            else:
                market, basis = "pending", "仅有平台中国标签，企业注册与融资主体证据不足"
            status = "accessible" if access.get("accessible") else ("thin_content" if access.get("http_status") == 200 else ("inaccessible" if url in access_by_url else "not_requested"))
            source_record_id = uid(f"space-record:{record['id']}")
            con.execute("INSERT INTO v12_source_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                source_record_id,"SpaceDaily",str(record["id"]),name,record.get("ce"),record.get("d") or "",record.get("r") or "未披露",record.get("at") or "未披露",
                json.dumps(record.get("iv") or [],ensure_ascii=False),record.get("s") or "未分类",record.get("ss"),record.get("st") or "",url,
                f"https://fund.spacedaily.com.cn/#deal-{record['id']}",record.get("co"),market,basis,status,json.dumps(record,ensure_ascii=False),space["generated_at"],
            ))
            if record not in space["target_records"]:
                continue
            round_value = record.get("r") or "未披露"
            if round_value in ALLOWED:
                candidate_status = "excluded_market" if market == "not_china" else ("duplicate_v1_v11" if match or formal_hit else "new")
            else:
                candidate_status = "pending_scope" if round_value in {"其他","战略融资"} else "excluded_round"
            body = access.get("text", "")
            key = compact(name)[:8]
            body_confirms = bool(access.get("accessible") and (key and key in compact(body)) and re.search(r"融资|投资", body))
            alternate_confirms = bool(match)
            verification = "verified" if body_confirms and market in {"confirmed_china","probable_china"} else ("partially_verified" if body_confirms or alternate_confirms else "pending")
            grade = "B" if body_confirms or alternate_confirms else "C"
            primary, secondary = category(record.get("s") or "")
            candidate_id = uid(f"space-candidate:{record['id']}")
            duplicate_event = match.get("duplicate_event_id") if match else (formal_hit.get("event_id") if formal_hit else None)
            con.execute("INSERT INTO v12_funding_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                candidate_id,name,None,record.get("d") or "",round_value,normalized_round(round_value),record.get("at") or "未披露",
                json.dumps(record.get("iv") or [],ensure_ascii=False),record.get("s") or "未分类",primary,secondary,record.get("st") or "",url,"SpaceDaily",source_record_id,
                grade,verification,candidate_status,match.get("candidate_id") if match else None,duplicate_event,
                "企业法定全称、融资主体、投资方角色、实际交割日期" if verification != "verified" else "企业法定全称及实际交割日期仍需官方来源确认",
                f"原始链接状态={status}；市场判断={market}。" + ("与V1.1投资界候选匹配。" if match else "未与V1.1确定匹配。"),timestamp,
            ))
            con.execute("INSERT INTO v12_candidate_source_links VALUES (?,?,?,?,?,?,?,?,?)", (uid(f"link:{candidate_id}:{url}"),candidate_id,"SpaceDaily原始链接",url,record.get("st") or "",grade,"primary" if body_confirms else "discovery_only",status,timestamp))
            if match:
                con.execute("INSERT OR IGNORE INTO v12_candidate_source_links VALUES (?,?,?,?,?,?,?,?,?)", (uid(f"link:{candidate_id}:{match['original_url']}"),candidate_id,"投资界",match["original_url"],match["title"],"B","supporting","accessible",timestamp))
            space_candidates.append({"candidate_id":candidate_id,"name":name,"date":record.get("d") or "","round":round_value,"title":record.get("st") or "","url":url})

        prior_platform_candidates: list[dict] = []
        for platform, audit in platforms["platforms"].items():
            robots_text = audit["robots"].get("text", "")
            con.execute("INSERT INTO v12_platform_audits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                platform,audit["base_url"],"accessible" if audit["robots"].get("http_status")==200 else "unavailable",
                "yes" if audit["public_event_list"] else "not_confirmed","yes" if audit["public_date_filter"] else "not_confirmed",
                "yes" if audit["public_pagination"] else "not_confirmed","partial" if audit["accessible_articles"] else "none",
                2,audit["search_clues"],0,audit["search_clues"]-audit["accessible_articles"],
                "法定主体、结构化投资方角色和交易日期通常不可直接获得","公开首页/robots及限定域名新闻检索；搜索结果不作为证据。" + ("存在登录或会员信号。" if audit["login_or_paywall_signal"] else ""),platforms["generated_at"],
            ))
            target_count = 0
            for article in audit["articles"]:
                if not article.get("accessible") or WEEKLY.search(article["title"]):
                    continue
                if not re.search(r"完成|宣布完成|获.{0,12}(?:融资|投资)",article["title"]):
                    continue
                found = ROUND_RE.search(article["title"])
                if not found:
                    continue
                published = email.utils.parsedate_to_datetime(article["published_at"]).date().isoformat() if article.get("published_at") else ""
                if not ("2026-11-01" <= published <= "2026-11-25"):
                    continue
                round_original, round_norm = round_from_title(article["title"])
                if round_original == "战略融资":
                    status = "pending_scope"
                else:
                    status = "new"
                name = company_from_title(article["title"])
                match = v11_match(name,published,round_original,article["title"])
                formal_hit = formal_match(name,published,round_original)
                matched_space = None
                for candidate in space_candidates:
                    if dates_close(published,candidate["date"]) and (same_company(name,candidate["name"]) or SequenceMatcher(None,compact(article["title"]),compact(candidate["title"])).ratio()>=0.75):
                        matched_space = candidate; break
                prior_hit = next((x for x in prior_platform_candidates if dates_close(published,x["date"]) and same_company(name,x["name"]) and target_round_matches(round_original,x["round"])),None)
                if match or matched_space or formal_hit or prior_hit:
                    status = "duplicate_v1_v11"
                candidate_id = uid(f"platform-candidate:{platform}:{article['original_url']}")
                primary, secondary = category("未分类")
                amount_match = AMOUNT_RE.search(article["title"])
                con.execute("INSERT INTO v12_funding_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    candidate_id,name,None,published,round_original,round_norm,amount_match.group(1) if amount_match else "未披露","[]","未分类",primary,secondary,
                    article["title"],article["original_url"],platform,None,"B","partially_verified",status,
                    match.get("candidate_id") if match else (matched_space["candidate_id"] if matched_space else (prior_hit["candidate_id"] if prior_hit else None)),match.get("duplicate_event_id") if match else (formal_hit.get("event_id") if formal_hit else None),
                    "企业法定全称、投资方及角色、融资实际发生日期","平台原文可访问并明确披露融资；仍需企业或投资机构官方来源核验。",timestamp,
                ))
                con.execute("INSERT INTO v12_candidate_source_links VALUES (?,?,?,?,?,?,?,?,?)", (uid(f"link:{candidate_id}:{article['original_url']}"),candidate_id,platform,article["original_url"],article["title"],"B","primary","accessible",timestamp))
                if match:
                    con.execute("INSERT OR IGNORE INTO v12_candidate_source_links VALUES (?,?,?,?,?,?,?,?,?)", (uid(f"link:{candidate_id}:{match['original_url']}"),candidate_id,"投资界",match["original_url"],match["title"],"B","supporting","accessible",timestamp))
                target_count += 1
                prior_platform_candidates.append({"candidate_id":candidate_id,"name":name,"date":published,"round":round_original})
            con.execute("UPDATE v12_platform_audits SET target_candidates=? WHERE platform=?", (target_count,platform))
        cls_articles = platforms["platforms"].get("财联社",{}).get("articles",[])
        for marker,buyer,target,ratio,amount in (
            ("艾为电子：拟收购模拟芯片公司钰泰半导体100%股份","艾为电子","钰泰半导体","100%","未披露"),
            ("斯菱智驱拟10.51亿元收购银球科技剩余75.66%股权","斯菱智驱","银球科技","75.66%","10.51亿元"),
        ):
            article = next((x for x in cls_articles if marker in x.get("title","") and x.get("accessible")),None)
            if not article:
                continue
            published = email.utils.parsedate_to_datetime(article["published_at"]).date().isoformat()
            con.execute("INSERT INTO v12_acquisition_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                uid(f"ma:{buyer}:{target}:{published}"),buyer,target,published,"equity_acquisition",ratio,amount,"announced",
                article["title"],article["original_url"],"财联社","B","partially_verified","需补上市公司/交易所公告、董事会审议状态及交割进度",timestamp,
            ))
    stats = {"source_records":con.execute("SELECT COUNT(*) FROM v12_source_records").fetchone()[0],"space_candidates":con.execute("SELECT COUNT(*) FROM v12_funding_candidates WHERE source_platform='SpaceDaily'").fetchone()[0],"platform_candidates":con.execute("SELECT COUNT(*) FROM v12_funding_candidates WHERE source_platform<>'SpaceDaily'").fetchone()[0],"new_independent":con.execute("SELECT COUNT(*) FROM v12_funding_candidates WHERE source_platform<>'SpaceDaily' AND candidate_status='new'").fetchone()[0]}
    con.close()
    print(json.dumps(stats,ensure_ascii=False))


if __name__ == "__main__":
    main()
