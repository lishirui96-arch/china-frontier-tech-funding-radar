from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import httpx


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "pedaily_v11_crawl.json"
HEADERS = {"User-Agent": "FundingRadarResearch/1.1 (+public-source-audit; low-frequency)"}
START, END = "2026-11-01", "2026-11-25"
MAX_PAGES = 40
INTERVAL = 0.45
COLUMNS = {
    "funding_major": "https://www.pedaily.cn/media/m830/",
    "investment_events": "https://www.pedaily.cn/vcpeevent/",
    "angel_early": "https://www.pedaily.cn/i-angel/",
    "ma_events": "https://www.pedaily.cn/capitalevent/maevent/",
}

ARTICLE_RE = re.compile(
    r'<h3[^>]*>\s*<a[^>]+href="(?P<url>https?://(?:news\.)?pedaily\.cn/[^\"]+)"[^>]*>'
    r'(?P<title>.*?)</a>\s*</h3>.*?class="date"[^>]*>.*?(?P<date>20\d{2}-\d{2}-\d{2})',
    re.I | re.S,
)
TAG_RE = re.compile(r"<[^>]+>")


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value))).strip()


def page_url(base: str, page: int) -> str:
    return base if page == 1 else urljoin(base, f"{page}/")


def article_rows(body: str) -> list[dict]:
    rows = []
    seen = set()
    for match in ARTICLE_RE.finditer(body):
        url = match.group("url").split("?")[0]
        if url in seen:
            continue
        seen.add(url)
        rows.append({"url": url, "title": clean(match.group("title")), "published_date": match.group("date")})
    return rows


def article_text(body: str) -> tuple[str, str]:
    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.I | re.S)
    title = clean(title_match.group(1)) if title_match else ""
    candidates = re.findall(
        r'<(?:div|article)[^>]+class="[^"]*(?:news-content|article-content|content|detail)[^"]*"[^>]*>(.*?)</(?:div|article)>',
        body,
        re.I | re.S,
    )
    text = max((clean(x) for x in candidates), key=len, default="")
    if len(text) < 300:
        text = clean(re.sub(r"<(?:script|style|nav|footer|header)[^>]*>.*?</(?:script|style|nav|footer|header)>", " ", body, flags=re.I | re.S))
    return title, text[:50000]


def main() -> None:
    result = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "window": {"start": START, "end": END},
        "robots": {},
        "pages": [],
        "articles": [],
    }
    article_map: dict[str, dict] = {}
    with httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True) as client:
        robots = client.get("https://www.pedaily.cn/robots.txt")
        result["robots"] = {"url": str(robots.url), "http_status": robots.status_code, "text": robots.text[:5000]}
        time.sleep(INTERVAL)
        for column, base in COLUMNS.items():
            old_pages = 0
            for page in range(1, MAX_PAGES + 1):
                url = page_url(base, page)
                try:
                    response = client.get(url)
                    rows = article_rows(response.text) if response.status_code == 200 else []
                    dates = [row["published_date"] for row in rows]
                    result["pages"].append({
                        "column": column, "page": page, "url": url,
                        "http_status": response.status_code, "article_count": len(rows),
                        "newest_date": max(dates, default=""), "oldest_date": min(dates, default=""),
                    })
                except Exception as exc:
                    result["pages"].append({"column": column, "page": page, "url": url, "http_status": None, "article_count": 0, "error": f"{type(exc).__name__}: {exc}"})
                    break
                for row in rows:
                    if START <= row["published_date"] <= END:
                        item = article_map.setdefault(row["url"], {**row, "columns": []})
                        if column not in item["columns"]:
                            item["columns"].append(column)
                if rows and max(dates) < START:
                    old_pages += 1
                else:
                    old_pages = 0
                if old_pages >= 2 or not rows:
                    break
                time.sleep(INTERVAL)
        for item in article_map.values():
            try:
                response = client.get(item["url"])
                title, text = article_text(response.text) if response.status_code == 200 else ("", "")
                item.update({"http_status": response.status_code, "final_url": str(response.url), "page_title": title, "page_text": text, "accessible": response.status_code == 200 and len(text) >= 300})
            except Exception as exc:
                item.update({"http_status": None, "accessible": False, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(INTERVAL)
    result["articles"] = sorted(article_map.values(), key=lambda x: (x["published_date"], x["url"]), reverse=True)
    result["stats"] = {
        "pages_traversed": len(result["pages"]),
        "unique_window_articles": len(result["articles"]),
        "accessible_articles": sum(bool(x.get("accessible")) for x in result["articles"]),
        "column_memberships": {key: sum(key in x["columns"] for x in result["articles"]) for key in COLUMNS},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
