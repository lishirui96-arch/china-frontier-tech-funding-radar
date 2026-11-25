from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work" / "spacedaily_v11_audit.json"
OUT = ROOT / "work" / "spacedaily_originals_v11.json"
TAG_RE = re.compile(r"<[^>]+>")


def clean(body: str) -> str:
    body = re.sub(r"<(?:script|style|nav|footer|header)[^>]*>.*?</(?:script|style|nav|footer|header)>", " ", body, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", body))).strip()


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    records = []
    seen = set()
    with httpx.Client(headers={"User-Agent": "FundingRadarResearch/1.1 (+public-source-verification; low-frequency)"}, timeout=20, follow_redirects=True) as client:
        for item in source["target_records"]:
            url = item.get("su") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            row = {"url": url, "record_ids": [x["id"] for x in source["target_records"] if x.get("su") == url]}
            try:
                response = client.get(url)
                content_type = response.headers.get("content-type", "")
                text = clean(response.text)[:50000] if response.status_code == 200 and "html" in content_type else ""
                row.update({"http_status": response.status_code, "final_url": str(response.url), "content_type": content_type, "text": text, "accessible": response.status_code == 200 and len(text) >= 300})
            except Exception as exc:
                row.update({"http_status": None, "accessible": False, "error": f"{type(exc).__name__}: {exc}"})
            records.append(row)
            time.sleep(0.35)
    result = {"generated_at": datetime.now().astimezone().isoformat(), "records": records, "stats": {"unique_urls": len(records), "accessible": sum(x["accessible"] for x in records), "unavailable": sum(not x["accessible"] for x in records)}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
