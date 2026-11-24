from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from funding_radar.db import connect
from funding_radar.repository import now, uid


TRACKING_KEYS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "spm", "from"}


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Invalid public URL: {url}")
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def content_hash(title: str, summary: str) -> str:
    return hashlib.sha256(f"{title.strip()}\n{summary.strip()}".encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ImportItem:
    url: str
    title: str
    source_name: str
    published_at: str | None = None
    summary: str = ""


def parse_csv_bytes(data: bytes) -> list[ImportItem]:
    text = data.decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text))
    required = {"url", "title", "source_name"}
    if not required.issubset(rows.fieldnames or []):
        raise ValueError("CSV requires url,title,source_name columns")
    return [ImportItem(r["url"], r["title"], r["source_name"], r.get("published_at") or None, r.get("summary") or "") for r in rows]


def _source_for(connection, name: str, domain: str) -> dict:
    row = connection.execute("SELECT * FROM sources WHERE lower(name)=lower(?) OR lower(base_url)=lower(?) ORDER BY is_active DESC LIMIT 1", (name, domain)).fetchone()
    if row:
        return dict(row)
    source_id = uid()
    connection.execute("INSERT INTO sources(source_id,name,source_type,source_family,evidence_default_grade,base_url,terms_status,created_at,is_active,allowed_scope,min_interval_seconds,failure_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)", (source_id, name, "unclassified", "manual", "D", domain, "review_required", now(), 1, "metadata_only", 3600))
    return dict(connection.execute("SELECT * FROM sources WHERE source_id=?", (source_id,)).fetchone())


def import_items(items: list[ImportItem], actor: str, path: Path | None = None, import_type: str = "bulk_url") -> dict:
    batch_id, inserted, duplicates, failures = uid(), 0, 0, []
    connection = connect(path)
    started = now()
    try:
        with connection:
            for item in items:
                try:
                    canonical = canonicalize_url(item.url)
                    domain = urlsplit(canonical).netloc
                    source = _source_for(connection, item.source_name.strip() or domain, domain)
                    existing = connection.execute("SELECT document_id FROM raw_documents WHERE canonical_url=?", (canonical,)).fetchone()
                    if existing:
                        duplicates += 1
                        continue
                    document_id = uid()
                    connection.execute("""INSERT INTO raw_documents(document_id,source_id,original_url,canonical_url,title,published_at,fetched_at,text_or_summary,content_hash,source_family,archive_status,parser_version,relevance_status,review_status,created_at,source_domain,fetch_status,financing_category,event_link_status,imported_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (document_id, source["source_id"], item.url.strip(), canonical, item.title.strip(), item.published_at, started, item.summary.strip() or None, content_hash(item.title, item.summary), source["source_family"], "summary_saved" if item.summary else "metadata_only", "manual-import-v1", "pending", "discovered", started, domain, "manual", "undetermined", "unlinked", started))
                    inserted += 1
                except Exception as exc:
                    failures.append({"url": item.url, "error": str(exc)})
            connection.execute("INSERT INTO import_batches VALUES (?,?,?,?,?,?,?,?,?,?)", (batch_id, import_type, actor, len(items), inserted, duplicates, len(failures), json.dumps(failures, ensure_ascii=False), started, now()))
    finally:
        connection.close()
    return {"batch_id": batch_id, "submitted": len(items), "inserted": inserted, "duplicates": duplicates, "failed": len(failures), "errors": failures}

