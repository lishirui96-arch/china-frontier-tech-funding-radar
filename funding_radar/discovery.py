from __future__ import annotations

import email.utils
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

from funding_radar.db import connect
from funding_radar.ingestion import ImportItem, import_items
from funding_radar.repository import now, uid


USER_AGENT = "FundingRadarResearch/1.1 (+local-audit; respectful-low-frequency)"


def discover_rss(source_id: str, feed_url: str, actor: str, max_requests: int = 2, path: Path | None = None) -> dict:
    if max_requests < 1 or max_requests > 5:
        raise ValueError("Per-run request budget must be 1..5")
    connection = connect(path)
    source = connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone()
    if not source or not source["is_active"]:
        connection.close(); raise ValueError("Source is missing or inactive")
    last = source["last_fetch_at"]
    if last and datetime.now(timezone.utc) < datetime.fromisoformat(last) + timedelta(seconds=source["min_interval_seconds"]):
        connection.close(); return {"status":"skipped","reason":"minimum interval not reached","request_count":0}
    run_id, started, failures = uid(), now(), []
    with connection:
        connection.execute("INSERT INTO discovery_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id,source_id,"rss",started,None,0,0,0,0,"rss-v1","running",None,None))
    try:
        robots_url = urljoin(feed_url, "/robots.txt")
        robots = urllib.robotparser.RobotFileParser(robots_url)
        robots.read()
        if not robots.can_fetch(USER_AGENT, feed_url):
            raise PermissionError("robots policy does not allow this feed")
        request = urllib.request.Request(feed_url, headers={"User-Agent":USER_AGENT})
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(2_000_000)
        root = ET.fromstring(payload)
        items = []
        for node in root.findall(".//item")[:50]:
            url = (node.findtext("link") or "").strip()
            title = (node.findtext("title") or "").strip()
            if url and title:
                items.append(ImportItem(url,title,source["name"],node.findtext("pubDate"),node.findtext("description") or ""))
        outcome = import_items(items,actor,path,"bulk_url")
        status = "success" if not outcome["failed"] else "partial"
        with connection:
            connection.execute("UPDATE discovery_runs SET completed_at=?,request_count=1,inserted_count=?,duplicate_count=?,failure_count=?,status=? WHERE discovery_run_id=?", (now(),outcome["inserted"],outcome["duplicates"],outcome["failed"],status,run_id))
            connection.execute("UPDATE sources SET last_fetch_at=?,failure_count=failure_count+? WHERE source_id=?", (now(),outcome["failed"],source_id))
        return {"run_id":run_id,"status":status,"request_count":1,**outcome}
    except Exception as exc:
        with connection:
            failure_id = uid()
            connection.execute("INSERT INTO discovery_failures VALUES (?,?,?,?,?,?,?)", (failure_id,run_id,feed_url,type(exc).__name__,str(exc),1,(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),now()))
            connection.execute("UPDATE discovery_runs SET completed_at=?,request_count=1,failure_count=1,status='failed',failure_summary=?,next_allowed_at=? WHERE discovery_run_id=?", (now(),str(exc),(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),run_id))
            connection.execute("UPDATE sources SET last_fetch_at=?,failure_count=failure_count+1 WHERE source_id=?", (now(),source_id))
        return {"run_id":run_id,"status":"failed","request_count":1,"error":str(exc)}
    finally:
        connection.close()
