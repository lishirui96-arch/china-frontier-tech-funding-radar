from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from funding_radar.db import connect
from funding_radar.migrations import migrate


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "work" / "v35_pedaily_cache"
NAMESPACE = uuid.UUID("11c42095-4eec-57bd-b0a1-d782f16c0b1e")
ARCHIVE = "https://www.pedaily.cn/vcpeevent/{page}/"
USER_AGENT = "ChinaFrontierFundingRadar/3.5 (public historical research; contact: local project)"

TARGET_ROUND_RE = re.compile(
    r"(?<![A-Za-z])(?:Pre[-－— ]?[AB](?:\+)?|[AB](?:(?:\+{1,2})|\d+)?|种子|天使(?:\+{1,2})?)轮",
    re.I,
)
NON_TARGET_ROUND_RE = re.compile(
    r"(?:Pre[-－— ]?C|[C-H](?:(?:\+{1,2})|\d+)?|基石|债权|可转债|并购)轮|"
    r"IPO|上市|收购|战略(?:轮|融资|投资)|产业基金|基金设立",
    re.I,
)
PENDING_ROUND_RE = re.compile(r"(?:完成|获得|获|宣布).{0,18}(?:融资|投资)|(?:融资|投资).{0,18}(?:完成|交割)")

STRONG_TECH = (
    "人工智能", "AI", "大模型", "智能体", "Agent", "算法", "算力", "数据基础设施", "数据库",
    "半导体", "芯片", "集成电路", "晶圆", "光刻", "封装", "EDA", "传感器", "光电子", "光通信",
    "机器人", "具身", "自动驾驶", "无人驾驶", "智能汽车", "激光雷达", "机器视觉", "工业软件",
    "生物技术", "生物制造", "合成生物", "创新药", "细胞治疗", "基因", "蛋白", "核酸", "医疗器械",
    "脑机", "神经", "量子", "卫星", "航天", "火箭", "低空", "无人机", "eVTOL", "飞行器",
    "核聚变", "新能源", "储能", "电池", "光伏", "氢能", "碳捕集", "新材料", "纳米材料",
    "先进制造", "智能制造", "高端装备", "精密仪器", "增材制造", "3D打印", "工业自动化",
    "网络安全", "信息安全", "农业科技", "食品科技", "环境科技", "清洁技术",
)
WEAK_TECH = (
    "科技", "智能", "数字化", "软件", "云计算", "物联网", "平台", "系统", "材料", "设备", "医药", "医疗",
)
CONSUMER = (
    "餐饮", "茶饮", "咖啡", "零食", "食品品牌", "服装", "美妆", "护肤", "酒店", "旅游", "酒业", "白酒",
    "连锁门店", "零售品牌", "宠物食品", "珠宝", "潮玩", "母婴", "家居品牌", "健身品牌", "房地产",
)
FOREIGN = (
    "总部位于美国", "总部位于英国", "总部位于法国", "总部位于德国", "总部位于印度", "总部位于巴西",
    "美国公司", "英国公司", "法国公司", "德国公司", "印度公司", "巴西公司", "新加坡公司", "以色列公司",
)

INDUSTRIES = {
    "机器人与具身智能": ("机器人", "具身", "机械臂", "灵巧手", "减速器", "伺服", "机器视觉"),
    "AI计算与半导体": ("半导体", "芯片", "集成电路", "算力", "光通信", "光电子", "晶圆", "封装", "EDA", "GPU"),
    "AI软件与工业智能": ("人工智能", "大模型", "AI", "Agent", "智能体", "工业软件", "数据库", "网络安全", "云计算"),
    "新能源与先进材料": ("新能源", "储能", "电池", "光伏", "氢能", "核聚变", "新材料", "纳米材料", "碳捕集"),
    "高端装备与先进制造": ("高端装备", "先进制造", "智能制造", "精密仪器", "工业自动化", "3D打印", "增材制造", "传感器"),
    "商业航天与卫星应用": ("航天", "火箭", "卫星", "星座"),
    "低空经济与无人系统": ("低空", "无人机", "eVTOL", "飞行器", "自动驾驶", "无人驾驶"),
    "生物制造与生命科学": ("生物", "创新药", "细胞", "基因", "蛋白", "核酸", "医疗器械", "医药"),
    "脑科学与神经技术": ("脑机", "神经科学", "神经调控", "脑科学"),
    "量子科技": ("量子",),
}


@dataclass(frozen=True)
class ArchiveItem:
    published_date: str
    title: str
    url: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(kind: str, value: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}|{value}"))


def days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def months(start: date, end: date) -> Iterable[tuple[date, date]]:
    current = start.replace(day=1)
    while current <= end:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield max(start, current), min(end, next_month - timedelta(days=1))
        current = next_month


def get(url: str, *, attempts: int = 4) -> bytes:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=25)
            response.raise_for_status()
            return response.content
        except Exception as exc:  # pragma: no cover - network retry path
            error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {error}")


def parse_archive(content: bytes) -> list[ArchiveItem]:
    soup = BeautifulSoup(content, "html.parser", from_encoding="utf-8")
    result = []
    for node in soup.select("#newslist-all li"):
        anchor = node.select_one("h3 a")
        stamp = node.select_one(".date")
        if not anchor or not stamp:
            continue
        day = stamp.get_text(" ", strip=True)[:10]
        url = anchor.get("href", "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) and url:
            result.append(ArchiveItem(day, anchor.get_text(" ", strip=True), url))
    return result


def discover(start: date, end: date, *, max_pages: int = 130) -> list[ArchiveItem]:
    CACHE.mkdir(parents=True, exist_ok=True)
    found: dict[str, ArchiveItem] = {}
    passed_start = False
    for page in range(1, max_pages + 1):
        path = CACHE / f"archive_{page:03d}.html"
        content = path.read_bytes() if path.exists() else get(ARCHIVE.format(page=page))
        if not path.exists():
            path.write_bytes(content)
        entries = parse_archive(content)
        if not entries:
            if passed_start:
                break
            continue
        oldest = min(date.fromisoformat(x.published_date) for x in entries)
        newest = max(date.fromisoformat(x.published_date) for x in entries)
        if newest < start:
            break
        if oldest <= start:
            passed_start = True
        for entry in entries:
            event_date = date.fromisoformat(entry.published_date)
            if start <= event_date <= end:
                found[entry.url] = entry
    return sorted(found.values(), key=lambda x: (x.published_date, x.url))


def article_cache_path(url: str) -> Path:
    article_id = re.search(r"/(\d+)\.shtml", url)
    name = article_id.group(1) if article_id else hashlib.sha256(url.encode()).hexdigest()
    return CACHE / "articles" / f"{name}.html"


def fetch_article(entry: ArchiveItem) -> tuple[ArchiveItem, str, str | None]:
    path = article_cache_path(entry.url)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        content = path.read_bytes() if path.exists() else get(entry.url)
        if not path.exists():
            path.write_bytes(content)
        soup = BeautifulSoup(content, "html.parser", from_encoding="utf-8")
        node = soup.select_one(".news-content") or soup.select_one("#news-content")
        if not node:
            return entry, "", "article body not found"
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        return entry, text, None
    except Exception as exc:  # pragma: no cover - network failure path
        return entry, "", str(exc)


def fetch_articles(entries: list[ArchiveItem], workers: int = 8) -> dict[str, tuple[str, str | None]]:
    result: dict[str, tuple[str, str | None]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch_article, entry) for entry in entries]
        for future in as_completed(futures):
            entry, text, error = future.result()
            result[entry.url] = (text, error)
    return result


def normalize_round(value: str) -> str:
    value = value.replace("－", "-").replace("—", "-").replace(" ", "")
    value = re.sub(r"^pre", "Pre", value, flags=re.I)
    return value


def round_bucket(round_name: str) -> str:
    return "early" if round_name.startswith(("种子", "天使")) else "vc"


def company_from_title(title: str) -> str:
    clean = re.sub(r"(?:_|｜)投资界.*$", "", title).strip(" “”，,：《》")
    clean = re.sub(r"^(?:(?:独家|首发|消息称)\s*[|｜:：]?\s*)+", "", clean)
    completed = re.search(r"([^，,|｜]{1,80}?)(?:宣布)?完成", clean)
    if completed:
        prefix = completed.group(1).strip(" “”，,：《》")
    else:
        parts = re.split(r"再获|获得|获|宣布|拿下|融资", clean, maxsplit=1)
        prefix = parts[0].strip(" “”，,：《》")
    quoted = re.findall(r"[「“\[]([^」”\]]+)[」”\]]", prefix)
    company = quoted[-1] if quoted else re.split(r"[，,：:]", prefix)[-1]
    company = company.strip(" “”，,：《》")
    company = re.sub(r"^(?:投资界\d*月\d日消息[:：]?)", "", company)
    return company[:80] or clean[:80]


def deduplicate_bulk_candidates() -> int:
    merged = 0
    with connect() as connection, connection:
        rows = connection.execute(
            """SELECT c.* FROM v35_historical_candidates c
               JOIN v35_collection_batches b USING(batch_id)
               WHERE b.created_by='v35_bulk_backfill'
               ORDER BY company_name,round_original,amount_original,announcement_date,candidate_id"""
        ).fetchall()
        groups: dict[tuple[str, str, str], list] = defaultdict(list)
        for row in rows:
            groups[(row["company_name"], row["round_original"], row["amount_original"])].append(row)
        for candidates in groups.values():
            canonical = candidates[0]
            for duplicate in candidates[1:]:
                distance = (date.fromisoformat(duplicate["announcement_date"]) - date.fromisoformat(canonical["announcement_date"])).days
                if distance > 30:
                    canonical = duplicate
                    continue
                connection.execute(
                    """DELETE FROM v35_candidate_sources WHERE candidate_id=? AND source_url IN
                       (SELECT source_url FROM v35_candidate_sources WHERE candidate_id=?)""",
                    (duplicate["candidate_id"], canonical["candidate_id"]),
                )
                connection.execute(
                    "UPDATE v35_candidate_sources SET candidate_id=? WHERE candidate_id=?",
                    (canonical["candidate_id"], duplicate["candidate_id"]),
                )
                connection.execute("DELETE FROM v35_classification_proposals WHERE candidate_id=?", (duplicate["candidate_id"],))
                connection.execute("DELETE FROM v35_historical_candidates WHERE candidate_id=?", (duplicate["candidate_id"],))
                merged += 1
        for batch in connection.execute("SELECT batch_id FROM v35_collection_batches WHERE created_by='v35_bulk_backfill'").fetchall():
            batch_id = batch["batch_id"]
            actual = connection.execute(
                """SELECT COUNT(*) total,
                          SUM(CASE WHEN round_bucket='vc' THEN 1 ELSE 0 END) vc,
                          SUM(CASE WHEN round_bucket='early' THEN 1 ELSE 0 END) early,
                          SUM(CASE WHEN round_bucket='pending' THEN 1 ELSE 0 END) pending
                   FROM v35_historical_candidates WHERE batch_id=?""", (batch_id,)
            ).fetchone()
            duplicate_sources = connection.execute(
                """SELECT COALESCE(SUM(source_count-1),0) FROM (
                     SELECT COUNT(*) source_count FROM v35_historical_candidates c
                     JOIN v35_candidate_sources s USING(candidate_id)
                     WHERE c.batch_id=? GROUP BY c.candidate_id HAVING COUNT(*)>1)""", (batch_id,)
            ).fetchone()[0]
            connection.execute(
                """UPDATE v35_collection_batches SET new_candidate_count=?,effective_event_count=?,
                   vc_event_count=?,early_event_count=?,pending_round_count=?,duplicate_source_count=?,updated_at=?
                   WHERE batch_id=?""",
                (actual["total"], actual["total"], actual["vc"] or 0, actual["early"] or 0,
                 actual["pending"] or 0, duplicate_sources, utc_now(), batch_id),
            )
    return merged


def amount_from_text(text: str) -> str:
    patterns = (
        r"(?:完成|获得|获|融资金额(?:为)?)[^。；]{0,30}?((?:近|超|逾|约)?\d+(?:\.\d+)?(?:亿|千万|百万|万)(?:元|美元|人民币|港元)?(?:级)?)",
        r"((?:数|近|超|逾|约)?(?:十|百|千)?(?:亿|千万|百万|万)(?:元|美元|人民币|港元)(?:级)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "未披露"


def investor_sentence(text: str) -> str:
    for sentence in re.split(r"[。！？]", text[:5000]):
        if any(word in sentence for word in ("领投", "跟投", "参投", "独家投资", "投资方")):
            return sentence.strip()[:600]
    return "未披露"


def classify(title: str, body: str) -> tuple[str, str | None, str]:
    scores = {
        name: 10 * sum(title.count(word) for word in words) + sum(body[:1200].count(word) for word in words)
        for name, words in INDUSTRIES.items()
    }
    name, score = max(scores.items(), key=lambda item: item[1])
    if score < 2:
        return "pending_judgment", None, "跨领域或新兴科技方向，现有一级领域无法可靠自动匹配"
    return "existing_taxonomy", name, f"正文技术关键词与{name}匹配"


def screen(entry: ArchiveItem, body: str, error: str | None) -> tuple[str, str, list[str]]:
    if error or not body:
        return "excluded", f"原文不可核验：{error or '正文为空'}", []
    text = f"{entry.title} {body[:3000]}"
    rounds = []
    for match in TARGET_ROUND_RE.finditer(entry.title):
        value = normalize_round(match.group(0))
        if value not in rounds:
            rounds.append(value)
    title_non_target = NON_TARGET_ROUND_RE.search(entry.title)
    if title_non_target:
        return "excluded", f"非目标轮次或交易类型：{title_non_target.group(0)}", []
    if not rounds:
        if PENDING_ROUND_RE.search(entry.title):
            rounds = ["轮次待核验"]
        else:
            return "excluded", "未识别到已完成融资事实或目标轮次", []
    if any(marker in text[:2500] for marker in FOREIGN):
        return "excluded", "正文显示为非中国企业", []
    strong = sum(1 for word in STRONG_TECH if word in text)
    weak = sum(1 for word in WEAK_TECH if word in text)
    consumer_title = any(word in entry.title for word in CONSUMER)
    if strong == 0 and weak < 2:
        return "excluded", "正文未显示实质科技创新属性", []
    if consumer_title and not any(word in entry.title for word in STRONG_TECH):
        return "excluded", "普通消费或传统服务企业，科技属性不足", []
    status = "needs_verification" if rounds == ["轮次待核验"] else "candidate"
    return status, "正文可访问；符合中国科技企业及目标融资口径", rounds


def taxonomy_ids(connection) -> dict[str, str]:
    return {row["name"]: row["industry_id"] for row in connection.execute(
        "SELECT industry_id,name FROM v30_industries WHERE taxonomy_version='V3.2'"
    )}


def insert_month(
    month_start: date,
    month_end: date,
    entries: list[ArchiveItem],
    articles: dict[str, tuple[str, str | None]],
    *,
    rebuild: bool = False,
) -> dict[str, int]:
    batch_key = f"{month_start.isoformat()}_{month_end.isoformat()}"
    batch_id = stable_id("batch", batch_key)
    timestamp = utc_now()
    counters = Counter()
    with connect() as connection, connection:
        if rebuild:
            connection.execute("DELETE FROM v35_classification_proposals WHERE candidate_id IN (SELECT candidate_id FROM v35_historical_candidates WHERE batch_id=?)", (batch_id,))
            connection.execute("DELETE FROM v35_candidate_sources WHERE candidate_id IN (SELECT candidate_id FROM v35_historical_candidates WHERE batch_id=?)", (batch_id,))
            connection.execute("DELETE FROM v35_historical_candidates WHERE batch_id=?", (batch_id,))
            connection.execute("DELETE FROM v35_collection_search_results WHERE batch_id=?", (batch_id,))
            connection.execute("DELETE FROM v35_collection_searches WHERE batch_id=?", (batch_id,))
            connection.execute("DELETE FROM v35_collection_batches WHERE batch_id=? AND created_by='v35_bulk_backfill'", (batch_id,))
        industry_ids = taxonomy_ids(connection)
        connection.execute(
            """INSERT OR IGNORE INTO v35_collection_batches
               (batch_id,batch_name,period_start,period_end,scope_note,status,created_by,created_at,updated_at)
               VALUES (?,?,?,?,?,'running','v35_bulk_backfill',?,?)""",
            (batch_id, f"V3.5历史回填 {batch_key}", month_start.isoformat(), month_end.isoformat(),
             "中国科技产业全领域；投资界融资频道逐日归档与正文核验；不使用V3.2分类作为搜索过滤条件",
             timestamp, timestamp),
        )
        by_day: dict[str, list[ArchiveItem]] = defaultdict(list)
        for entry in entries:
            by_day[entry.published_date].append(entry)
        for day in days(month_start, month_end):
            day_text = day.isoformat()
            count = len(by_day[day_text])
            valid = 0
            for entry in by_day[day_text]:
                body, error = articles[entry.url]
                status, _, _ = screen(entry, body, error)
                valid += status in {"candidate", "needs_verification"}
            search_id = stable_id("search", f"{batch_id}|{day_text}|pedaily")
            connection.execute(
                """INSERT OR REPLACE INTO v35_collection_searches
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (search_id, batch_id, day_text, "投资界", "融资频道逐日归档；正文核验目标轮次与全领域科技属性",
                 count, valid, "completed" if count else "no_result",
                 "公开归档逐页检索；无结果日期仍保留检索记录", timestamp),
            )
        for entry in entries:
            body, error = articles[entry.url]
            status, reason, rounds = screen(entry, body, error)
            result_id = stable_id("result", f"{batch_id}|{entry.url}")
            connection.execute(
                """INSERT OR REPLACE INTO v35_collection_search_results
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (result_id, batch_id, "投资界", entry.title, entry.url, entry.published_date,
                 status, reason, timestamp),
            )
            counters["raw"] += 1
            counters[status] += 1
            if status == "excluded":
                continue
            company = company_from_title(entry.title)
            amount = amount_from_text(f"{entry.title} {body[:4000]}")
            investors = investor_sentence(body)
            proposal_type, industry_name, proposal_reason = classify(entry.title, body)
            for round_name in rounds:
                event_key = f"{company}|{entry.published_date}|{round_name}"
                stable_event_id = stable_id("event", event_key)
                candidate_id = stable_id("candidate", f"{batch_id}|{event_key}")
                bucket = "pending" if round_name == "轮次待核验" else round_bucket(round_name)
                review_status = "needs_verification" if bucket == "pending" else "pending"
                connection.execute(
                    """INSERT OR IGNORE INTO v35_historical_candidates
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (candidate_id, batch_id, stable_event_id, company, entry.published_date, None,
                     round_name, bucket, amount, None, investors,
                     body[:500] or entry.title, body[:1200] or entry.title,
                     "B", review_status, "v35_bulk_backfill", timestamp, timestamp),
                )
                source_id = stable_id("candidate_source", f"{candidate_id}|{entry.url}")
                connection.execute(
                    """INSERT OR IGNORE INTO v35_candidate_sources
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (source_id, candidate_id, "投资界", entry.title, entry.url, entry.published_date,
                     body[:2000], 1, "text_saved",
                     hashlib.sha256(body.encode()).hexdigest(), timestamp),
                )
                proposal_id = stable_id("proposal", candidate_id)
                connection.execute(
                    """INSERT OR IGNORE INTO v35_classification_proposals
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (proposal_id, candidate_id, proposal_type, industry_name if not industry_name else None,
                     None, None, industry_ids.get(industry_name), None, None,
                     "基于公开正文的自动候选分类，不改变V3.2冻结体系",
                     "仅匹配一级领域；二三级技术边界留待后续审核" if industry_name else "现有十个一级领域无可靠匹配",
                     proposal_reason, 1, 1, "pending", "v35_bulk_backfill", timestamp),
                )
                counters["events"] += 1
                counters[bucket] += 1
        actual = connection.execute(
            """SELECT COUNT(*) total,
                      SUM(CASE WHEN round_bucket='vc' THEN 1 ELSE 0 END) vc,
                      SUM(CASE WHEN round_bucket='early' THEN 1 ELSE 0 END) early,
                      SUM(CASE WHEN round_bucket='pending' THEN 1 ELSE 0 END) pending
               FROM v35_historical_candidates WHERE batch_id=?""",
            (batch_id,),
        ).fetchone()
        duplicate_sources = connection.execute(
            """SELECT COALESCE(SUM(source_count - 1),0) FROM (
                 SELECT c.candidate_id,COUNT(*) source_count
                 FROM v35_historical_candidates c JOIN v35_candidate_sources s USING(candidate_id)
                 WHERE c.batch_id=? GROUP BY c.candidate_id HAVING COUNT(*)>1)""",
            (batch_id,),
        ).fetchone()[0]
        counters["events"] = actual["total"]
        counters["vc"] = actual["vc"] or 0
        counters["early"] = actual["early"] or 0
        counters["pending"] = actual["pending"] or 0
        counters["duplicate_sources"] = duplicate_sources
        connection.execute(
            """UPDATE v35_collection_batches SET status='completed',source_count=1,
               raw_source_count=?,new_candidate_count=?,duplicate_source_count=?,effective_event_count=?,
               vc_event_count=?,early_event_count=?,pending_round_count=?,pending_classification_count=?,
               started_at=COALESCE(started_at,?),completed_at=?,updated_at=? WHERE batch_id=?""",
            (counters["raw"], counters["events"], duplicate_sources, counters["events"], counters["vc"],
             counters["early"], counters["pending"], counters["events"], timestamp, timestamp, timestamp, batch_id),
        )
    return dict(counters)


def run(start: date, end: date, *, workers: int = 8, rebuild: bool = False) -> dict:
    if start > end:
        raise ValueError("start must not be after end")
    migrate()
    entries = discover(start, end)
    articles = fetch_articles(entries, workers=workers)
    monthly = {}
    for month_start, month_end in reversed(list(months(start, end))):
        selected = [item for item in entries if month_start <= date.fromisoformat(item.published_date) <= month_end]
        monthly[month_start.strftime("%Y-%m")] = insert_month(month_start, month_end, selected, articles, rebuild=rebuild)
        print(json.dumps({"month": month_start.strftime("%Y-%m"), **monthly[month_start.strftime("%Y-%m")]}, ensure_ascii=False), flush=True)
    merged = deduplicate_bulk_candidates()
    return {"start": start.isoformat(), "end": end.isoformat(), "archive_articles": len(entries), "deduplicated_events": merged, "months": monthly}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 12, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 26))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.start, args.end, workers=args.workers, rebuild=args.rebuild), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
