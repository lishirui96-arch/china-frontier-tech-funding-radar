from __future__ import annotations

import email.utils
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work" / "gnewsdecoder"))
from googlenewsdecoder import gnewsdecoder  # noqa: E402

OUT = ROOT / "work" / "independent_platforms_v12.json"
HEADERS = {"User-Agent": "FundingRadarResearch/1.2 (+public-source-audit; low-frequency)"}
PLATFORMS = {
    "36氪": {"base": "https://36kr.com/", "domains": ("36kr.com", "www.36kr.com")},
    "IT桔子": {"base": "https://www.itjuzi.com/", "domains": ("itjuzi.com", "www.itjuzi.com")},
    "清科": {"base": "https://www.pedata.cn/", "domains": ("pedata.cn", "www.pedata.cn")},
    "投中": {"base": "https://www.chinaventure.com.cn/", "domains": ("chinaventure.com.cn", "www.chinaventure.com.cn")},
    "财联社": {"base": "https://www.cls.cn/", "domains": ("cls.cn", "www.cls.cn")},
    "证券时报": {"base": "https://www.stcn.com/", "domains": ("stcn.com", "www.stcn.com")},
}
ROUND_RE = re.compile(r"种子轮|天使\+?轮|Pre[-－]?A\+?轮?|A\+\+?轮|A轮|Pre[-－]?B\+?轮?|B\+\+?轮|B轮|战略融资|融资|收购|并购")
TAG_RE = re.compile(r"<[^>]+>")


def text_only(value: str) -> str:
    value = re.sub(r"<(?:script|style|nav|footer|header)[^>]*>.*?</(?:script|style|nav|footer|header)>", " ", value, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


def fetch(client: httpx.Client, url: str) -> tuple[dict, str]:
    try:
        response = client.get(url)
        body = response.text
        return ({"url": url, "final_url": str(response.url), "http_status": response.status_code, "content_type": response.headers.get("content-type", ""), "length": len(response.content)}, body)
    except Exception as exc:
        return ({"url": url, "http_status": None, "error": f"{type(exc).__name__}: {exc}"}, "")


def rss(client: httpx.Client, domain: str) -> list[dict]:
    queries = [
        f"site:{domain} (融资 OR 天使轮 OR Pre-A OR A轮 OR B轮)",
        f"site:{domain} (收购 OR 并购 OR 资产重组)",
    ]
    found = {}
    for query in queries:
        url = "https://news.google.com/rss/search?q=" + quote(query + " after:2026-11-01 before:2026-11-26") + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        meta, body = fetch(client, url)
        if meta.get("http_status") != 200:
            continue
        root = ET.fromstring(body)
        for node in root.findall("./channel/item"):
            title = node.findtext("title") or ""
            link = node.findtext("link") or ""
            published = node.findtext("pubDate") or ""
            if not ROUND_RE.search(title):
                continue
            item = {"query": query, "title": title.rsplit(" - ", 1)[0], "google_url": link, "published_at": published}
            found.setdefault(link, item)
        time.sleep(0.4)
    return list(found.values())


def main() -> None:
    result = {"generated_at": datetime.now().astimezone().isoformat(), "platforms": {}}
    with httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True) as client:
        for name, config in PLATFORMS.items():
            base = config["base"]
            robots_meta, robots = fetch(client, base.rstrip("/") + "/robots.txt")
            home_meta, home = fetch(client, base)
            rows = rss(client, config["domains"][0])
            decoded = gnewsdecoder([x["google_url"] for x in rows], timeout=20) if rows else []
            articles = []
            for item, decode in zip(rows, decoded):
                url = decode.get("decoded_url", "") if decode.get("success") else ""
                item["original_url"] = url
                item["decode_status"] = decode.get("status") or decode.get("message") or ""
                if url and any(urlparse(url).netloc.endswith(d) for d in config["domains"]):
                    meta, body = fetch(client, url)
                    body_text = text_only(body)[:50000] if meta.get("http_status") == 200 and "html" in meta.get("content_type", "") else ""
                    item.update(meta)
                    item["page_text"] = body_text
                    item["accessible"] = meta.get("http_status") == 200 and len(body_text) >= 300
                else:
                    item["accessible"] = False
                articles.append(item)
                time.sleep(0.35)
            lower_home = home.lower()
            result["platforms"][name] = {
                "base_url": base,
                "robots": {**robots_meta, "text": robots[:4000]},
                "homepage": home_meta,
                "public_event_list": bool(re.search(r"融资事件|投资事件|融资数据库|创投|投融资", home)),
                "public_date_filter": bool(re.search(r"日期|时间|year|date", home, re.I)),
                "public_pagination": bool(re.search(r"下一页|page=|/page/|pagination", home, re.I)),
                "login_or_paywall_signal": bool(re.search(r"登录|会员|付费|vip|login", lower_home, re.I)),
                "search_clues": len(articles),
                "accessible_articles": sum(x.get("accessible", False) for x in articles),
                "articles": articles,
            }
            time.sleep(0.5)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: {"clues": v["search_clues"], "accessible": v["accessible_articles"], "home": v["homepage"].get("http_status")} for k, v in result["platforms"].items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
