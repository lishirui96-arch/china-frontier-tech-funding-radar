from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "work" / "spacedaily_v11_audit.json"
BASE = "https://fund.spacedaily.com.cn/"
HEADERS = {"User-Agent": "FundingRadarResearch/1.1 (+public-source-audit; low-frequency)"}
TARGET_ROUNDS = {"天使轮", "Pre-A", "A轮", "A+轮", "B轮"}


def get(client: httpx.Client, url: str) -> tuple[dict, str]:
    try:
        response = client.get(url)
        return ({"url": url, "final_url": str(response.url), "http_status": response.status_code, "content_length": len(response.content)}, response.text)
    except Exception as exc:
        return ({"url": url, "http_status": None, "error": f"{type(exc).__name__}: {exc}"}, "")


def main() -> None:
    result = {"generated_at": datetime.now().astimezone().isoformat(), "pages": []}
    with httpx.Client(headers=HEADERS, timeout=25, follow_redirects=True) as client:
        robots_meta, robots = get(client, BASE + "robots.txt")
        home_meta, home = get(client, BASE)
        result["pages"].extend([robots_meta, home_meta])
        result["robots_text"] = robots
        for url in (
            "https://spacedaily.com.cn/data-methodology/",
            "https://spacedaily.com.cn/privacy-policy/",
            "https://spacedaily.com.cn/enterprise/",
            BASE + "sitemap.xml",
            BASE + "assets/app.js?v=1793265272",
        ):
            meta, body = get(client, url)
            meta["text_excerpt"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))[:1200]
            result["pages"].append(meta)
        match = re.search(r"window\.__DEALS\s*=\s*(\[.*?\]);\s*</script>", home, re.S)
        deals = json.loads(match.group(1)) if match else []
        november = [x for x in deals if "2026-11-01" <= (x.get("d") or "") <= "2026-11-25"]
        china = [x for x in november if x.get("co") == "中国"]
        target = [x for x in china if x.get("r") in TARGET_ROUNDS or x.get("r") in {"战略融资", "其他"}]
        result["technical_audit"] = {
            "public_html_embedded_dataset": bool(match),
            "public_json_api_found": False,
            "public_api_documentation_found": False,
            "public_export_found": False,
            "enterprise_export_api_link_present": "完整导出 / API" in home,
            "filters": {"region": True, "round": True, "year": True, "sector": True, "date_range": False},
            "client_side_pagination": False,
            "historical_records_in_public_html": True,
            "terms_link_found": bool(re.search(r"terms|服务条款|使用条款", home, re.I)),
            "privacy_link_found": "privacy-policy" in home,
        }
        result["stats"] = {"all_public_records": len(deals), "november_window": len(november), "china_labeled": len(china), "target_or_review_rounds": len(target)}
        result["target_records"] = target
        result["quality_flags"] = [
            "公开记录仅作发现线索，不能直接形成正式事件",
            "企业名称存在截断或错误抽取风险",
            "国家/地区字段存在误标风险，需以原文和企业注册信息复核",
            "融资日期可能是报道日期、月份占位日期或交易日期，需逐条复核",
            "轮次、投资方角色、金额与币种需回到原始来源复核",
            "完整导出/API属于机构版入口，本轮未访问受限功能",
        ]
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
