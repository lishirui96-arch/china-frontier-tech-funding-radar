from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from funding_radar.db import connect


CHINA_TZ = ZoneInfo("Asia/Shanghai")
DATE_ONLY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MONTH_ONLY = re.compile(r"^(\d{4})-(\d{2})$")


@dataclass(frozen=True)
class PublicRelease:
    release_id: str
    release_name: str
    created_at: str
    content_hash: str
    events: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PublicFilters:
    month: str = ""
    track_id: str = ""
    year: str = ""
    round_name: str = ""
    company: str = ""
    investor: str = ""
    page: int = 1
    page_size: int = 10


def china_month(value: str | None) -> str | None:
    """Return the natural month in China Standard Time for a confirmed date."""
    if not value:
        return None
    text = str(value).strip()
    match = DATE_ONLY.fullmatch(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CHINA_TZ)
    else:
        parsed = parsed.astimezone(CHINA_TZ)
    return parsed.strftime("%Y-%m")


def primary_track(event: dict[str, Any]) -> tuple[str, str]:
    explicit_id = event.get("primary_track_id") or event.get("track_id") or event.get("topic_id")
    explicit_name = event.get("primary_track_name") or event.get("track_name") or event.get("topic_name")
    if explicit_id or explicit_name:
        return str(explicit_id or explicit_name), str(explicit_name or explicit_id)
    tracks = event.get("tracks") or []
    primaries = [item for item in tracks if item.get("is_primary")]
    if len(primaries) == 1:
        item = primaries[0]
        return str(item.get("track_id") or item.get("name")), str(item.get("track_name") or item.get("name"))
    if len(tracks) == 1:
        item = tracks[0]
        return str(item.get("track_id") or item.get("name")), str(item.get("track_name") or item.get("name"))
    return "unclassified", "未分类"


def recent_months(month: str, count: int = 6) -> list[str]:
    match = MONTH_ONLY.fullmatch(month)
    if not match:
        raise ValueError("month must use YYYY-MM")
    year, number = int(match.group(1)), int(match.group(2))
    if not 1 <= number <= 12:
        raise ValueError("month must use YYYY-MM")
    values = []
    for offset in range(count - 1, -1, -1):
        absolute = year * 12 + number - 1 - offset
        values.append(f"{absolute // 12:04d}-{absolute % 12 + 1:02d}")
    return values


def aggregate_monthly_capital_flow(
    events: list[dict[str, Any]], industries: list[dict[str, Any]], month: str, *,
    currency: str = "", industry_id: str = "", round_name: str = "",
    updated_at: str | None = None,
) -> dict[str, Any]:
    """Aggregate only events already admitted by the strict release/confirmation gate."""
    months = recent_months(month)
    unique: dict[str, dict[str, Any]] = {}
    for raw in events:
        event_id = str(raw.get("event_id") or raw.get("confirmed_event_id") or "")
        if not event_id or event_id in unique:
            continue
        item = dict(raw)
        item["event_id"] = event_id
        item["month"] = china_month(item.get("announcement_date"))
        if not item["month"]:
            continue
        if currency and str(item.get("amount_currency") or "") != currency:
            continue
        if industry_id and str(item.get("primary_industry_id") or "") != industry_id:
            continue
        if round_name and str(item.get("round_normalized") or "") != round_name:
            continue
        unique[event_id] = item
    selected = list(unique.values())
    current = [item for item in selected if item["month"] == month]

    def valid_amount(item: dict[str, Any]) -> int | float | None:
        if item.get("is_cumulative_amount"):
            return None
        if item.get("amount_disclosure_type") != "exact":
            return None
        value = item.get("amount_exact")
        return value if isinstance(value, (int, float)) else None

    currencies = sorted({str(x.get("amount_currency")) for x in current if valid_amount(x) is not None and x.get("amount_currency")})
    trend_currencies = sorted({str(x.get("amount_currency")) for x in selected if x["month"] in months and valid_amount(x) is not None and x.get("amount_currency")})
    totals = {code: sum(valid_amount(x) or 0 for x in current if x.get("amount_currency") == code) for code in currencies}
    industry_names = {str(x["industry_id"]): str(x["name"]) for x in industries}
    industry_rows = []
    for item in industries:
        iid = str(item["industry_id"])
        matches = [x for x in current if x.get("primary_industry_id") == iid]
        amounts = {code: sum(valid_amount(x) or 0 for x in matches if x.get("amount_currency") == code) for code in currencies}
        industry_rows.append({
            "industry_id": iid, "industry_name": str(item["name"]),
            "event_count": len({x["event_id"] for x in matches}),
            "company_count": len({x.get("company_id") for x in matches if x.get("company_id")}),
            "amounts": amounts,
            "shares": {code: (amounts[code] / totals[code] if totals.get(code) else None) for code in currencies},
        })
    round_rows = []
    for name in sorted({str(x.get("round_normalized") or "未标准化") for x in current}):
        matches = [x for x in current if str(x.get("round_normalized") or "未标准化") == name]
        amounts = {code: sum(valid_amount(x) or 0 for x in matches if x.get("amount_currency") == code) for code in currencies}
        round_rows.append({"round": name, "event_count": len({x["event_id"] for x in matches}), "amounts": amounts,
                           "shares": {code: (amounts[code] / totals[code] if totals.get(code) else None) for code in currencies}})
    trend = []
    for value in months:
        matches = [x for x in selected if x["month"] == value]
        trend.append({"month": value, "event_count": len({x["event_id"] for x in matches}),
                      "amounts": {code: sum(valid_amount(x) or 0 for x in matches if x.get("amount_currency") == code) for code in trend_currencies}})
    classified = [x for x in current if x.get("primary_industry_id") in industry_names]
    disclosed = [x for x in current if valid_amount(x) is not None]
    ranged = [x for x in current if not x.get("is_cumulative_amount") and x.get("amount_disclosure_type") in {"bounded_range", "lower_bound", "upper_bound", "order_of_magnitude"}]
    undisclosed = [x for x in current if x.get("amount_disclosure_type") == "undisclosed"]
    cumulative = [x for x in current if x.get("is_cumulative_amount")]
    usd_events = [x for x in current if x.get("amount_currency") == "USD"]
    return {
        "scope": "formal_confirmed_release_only", "month": month, "is_mtd": month == datetime.now(CHINA_TZ).strftime("%Y-%m"),
        "filters": {"currency": currency or None, "industry_id": industry_id or None, "round": round_name or None},
        "totals": {"event_count": len(current), "amount_disclosed_event_count": len(disclosed),
                   "company_count": len({x.get("company_id") for x in current if x.get("company_id")}),
                   "industry_count": len({x.get("primary_industry_id") for x in classified}), "amounts": totals,
                   "amount_disclosure_coverage": len(disclosed) / len(current) if current else 0,
                   "unclassified_event_count": len(current) - len(classified),
                   "range_amount_event_count": len(ranged), "undisclosed_amount_event_count": len(undisclosed),
                   "cumulative_amount_event_count": len(cumulative), "usd_event_count": len(usd_events)},
        "industries": industry_rows, "rounds": round_rows, "trend": trend,
        "currencies": currencies, "trend_currencies": trend_currencies, "updated_at": updated_at,
        "methodology": ["仅统计人工确认且进入正式Release的唯一事件", "按announcement_date公告日期统计", "当前月为MTD口径",
                        "未披露、累计及非精确区间金额不计入金额汇总", "CNY与USD分币种统计，不直接相加"],
    }


def candidate_round_bucket(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    if any(token in normalized for token in ("seed", "angel", "种子", "天使")):
        return "early"
    if any(token in normalized for token in ("战略", "并购", "收购", "strategic")):
        return "strategic"
    if re.search(r"(?:pre[- ]?[ab]|[ab](?:\+{1,2}|\d)?)(?:轮)?", normalized):
        return "vc"
    return "other"


def rolling_window(events: list[dict[str, Any]], days: int, *, cutoff: str | None = None) -> dict[str, Any]:
    """Filter unique events to an inclusive rolling window based on disclosure date."""
    if days not in {30, 90, 360}:
        raise ValueError("window must be one of 30, 90, 360")
    dated: list[tuple[date, dict[str, Any]]] = []
    for event in events:
        raw = str(event.get("announcement_date") or event.get("disclosure_date") or "")
        if not DATE_ONLY.fullmatch(raw):
            continue
        dated.append((date.fromisoformat(raw), event))
    end = date.fromisoformat(cutoff) if cutoff else max((item[0] for item in dated), default=date.today())
    start = end - timedelta(days=days - 1)
    unique: dict[str, dict[str, Any]] = {}
    for event_date, event in dated:
        key = str(event.get("record_id") or event.get("unique_event_id") or event.get("event_id") or "")
        if key and start <= event_date <= end and key not in unique:
            unique[key] = event
    source_start = min((item[0] for item in dated), default=None)
    source_end = max((item[0] for item in dated), default=None)
    effective_start = max(start, source_start) if source_start else None
    complete = bool(source_start and source_start <= start)
    return {
        "days": days, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "events": list(unique.values()), "source_start_date": source_start.isoformat() if source_start else None,
        "source_end_date": source_end.isoformat() if source_end else None,
        "effective_start_date": effective_start.isoformat() if effective_start else None,
        "coverage_complete": complete,
    }


def candidate_round_structure(events: list[dict[str, Any]], industries: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    groups = [
        {"key": "vc", "label": "VC（Pre-A–B++）", "count": 0},
        {"key": "early", "label": "早期（种子/天使）", "count": 0},
        {"key": "strategic", "label": "战略投资 / 并购", "count": 0},
        {"key": "other", "label": "其他", "count": 0},
    ]
    lookup = {item["key"]: item for item in groups}
    grouped_events: dict[str, list[dict[str, Any]]] = {item["key"]: [] for item in groups}
    unique: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("record_id") or event.get("unique_event_id") or "")
        if key and key not in unique:
            unique[key] = event
    for event in unique.values():
        bucket = candidate_round_bucket(event.get("round_original"))
        lookup[bucket]["count"] += 1
        grouped_events[bucket].append(event)
    total = len(unique)
    industry_names = {row["industry_id"]: row["name"] for row in (industries or [])}
    for item in groups:
        item["share"] = item["count"] / total if total else 0
        bucket_events = grouped_events[item["key"]]
        industry_counts: dict[str, int] = {}
        for event in bucket_events:
            industry_id = str((event.get("classification") or {}).get("primary_industry_id") or "")
            if industry_id:
                industry_counts[industry_id] = industry_counts.get(industry_id, 0) + 1
        rows = [{"industry_id": industry_id, "industry_name": industry_names.get(industry_id, "待分类"),
                 "event_count": count, "share": count / item["count"] if item["count"] else 0}
                for industry_id, count in industry_counts.items()]
        item["industries"] = sorted(rows, key=lambda row: (-row["event_count"], row["industry_name"]))
        item["company_count"] = len({str(event.get("company_id")) for event in bucket_events if event.get("company_id")})
        item["industry_count"] = len(industry_counts)
    queues: dict[str, int] = {}
    for event in unique.values():
        queue = str(event.get("queue_class") or "未知")
        queues[queue] = queues.get(queue, 0) + 1
    return {"scope": "A_B_candidate_observation", "total": total, "groups": groups, "queue_counts": queues,
            "note": "VC口径包含Pre-A、A、A+、A++、Pre-B、B、B+、B++等成长阶段融资"}


def candidate_industry_structure(events: list[dict[str, Any]], industries: list[dict[str, Any]]) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("record_id") or event.get("unique_event_id") or "")
        if key and key not in unique:
            unique[key] = event
    counts: dict[str, int] = {}
    for event in unique.values():
        industry_id = str((event.get("classification") or {}).get("primary_industry_id") or "")
        if industry_id:
            counts[industry_id] = counts.get(industry_id, 0) + 1
    total = len(unique)
    rows = [{"industry_id": row["industry_id"], "industry_name": row["name"],
             "event_count": counts.get(row["industry_id"], 0),
             "share": counts.get(row["industry_id"], 0) / total if total else 0}
            for row in industries]
    rows.sort(key=lambda row: (-row["event_count"], row["industry_name"]))
    return {"scope": "A_B_candidate_observation", "total": total, "industries": rows,
            "classified": sum(row["event_count"] for row in rows),
            "unclassified": total - sum(row["event_count"] for row in rows),
            "company_count": len({str(event.get("company_id")) for event in unique.values() if event.get("company_id")}),
            "industry_count": sum(1 for row in rows if row["event_count"] > 0)}


def repeated_candidate_companies(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        company_id = str(event.get("company_id") or "")
        if company_id:
            grouped.setdefault(company_id, []).append(event)
    results = []
    for company_id, records in grouped.items():
        unique = {str(record.get("record_id") or record.get("unique_event_id") or ""): record for record in records}
        rows = list(unique.values())
        if len(rows) < 2:
            continue
        sources = {str(row.get("source_platform") or "") for row in rows}
        dates = {str(row.get("disclosure_date") or "") for row in rows}
        amounts = {str(row.get("amount_original") or "") for row in rows}
        rounds = {str(row.get("round_original") or "") for row in rows}
        if len(sources) == 1 and len(dates) == 1 and len(rounds) > 1:
            finding = "明确多轮融资"
            note = "同一来源在同一披露日明确列出不同融资轮次，按不同事件保留。"
        elif len(sources) > 1 and len(amounts) == 1:
            finding = "疑似重复来源"
            note = "不同来源披露金额相同但轮次或日期存在差异，需要人工核验是否为同一融资事件。"
        else:
            finding = "需要人工核验"
            note = "同一企业存在多条融资记录，需结合原始报道判断事件关系。"
        rows.sort(key=lambda row: (str(row.get("disclosure_date") or ""), str(row.get("record_id") or "")))
        results.append({"company_id": company_id, "company_name": rows[0].get("company_name_standard") or "未命名企业",
                        "finding": finding, "note": note, "records": rows})
    return sorted(results, key=lambda row: (row["finding"], row["company_name"]))


def merge_duplicate_candidate_events(
    events: list[dict[str, Any]], confirmed_duplicate_groups: dict[str, str] | None = None
) -> list[dict[str, Any]]:
    """Merge multi-round articles and cross-source reports of the same financing."""
    def merge_records(records: list[dict[str, Any]]) -> dict[str, Any]:
        records = sorted(records, key=lambda row: str(row.get("disclosure_date") or ""))
        item = dict(records[0])
        if len(records) == 1:
            return item

        def combined(field: str, ignored: set[str] | None = None) -> str:
            ignored = ignored or set()
            values = []
            for record in records:
                value = str(record.get(field) or "").strip()
                if value and value not in ignored and value not in values:
                    values.append(value)
            return " / ".join(values)

        item["round_original"] = combined("round_original") or "未披露"
        item["amount_original"] = combined("amount_original") or "未披露"
        item["investors_original"] = combined(
            "investors_original", {"未披露", "未结构化提取", "待结构化", "[]"}
        ) or "未披露"
        event_ids = []
        source_urls = []
        record_count = 0
        for record in records:
            ids = record.get("merged_event_ids") or [record.get("unique_event_id") or record.get("record_id")]
            event_ids.extend(str(value) for value in ids if value and str(value) not in event_ids)
            url = str(record.get("source_url") or "").strip()
            if url and url not in source_urls:
                source_urls.append(url)
            record_count += int(record.get("merged_record_count") or 1)
            if not item.get("classification", {}).get("primary_industry_id") and record.get("classification", {}).get("primary_industry_id"):
                item["classification"] = record["classification"]
        item["merged_event_ids"] = event_ids
        item["merged_source_urls"] = source_urls
        item["merged_record_count"] = record_count
        buckets = {candidate_round_bucket(record.get("round_original")) for record in records}
        item["round_bucket"] = next(iter(buckets)) if len(buckets) == 1 else "other"
        if any(record.get("review_status") == "needs_verification" for record in records):
            item["review_status"] = "needs_verification"
        return item

    confirmed_duplicate_groups = confirmed_duplicate_groups or {}
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for event in events:
        source_url = str(event.get("source_url") or "").strip()
        event_id = str(event.get("unique_event_id") or event.get("record_id") or "")
        confirmed_group = confirmed_duplicate_groups.get(event_id)
        key = (("confirmed", confirmed_group, "") if confirmed_group else (
            str(event.get("company_name_standard") or event.get("company_id") or "").strip(),
            str(event.get("disclosure_date") or event.get("announcement_date") or "").strip(),
            source_url or event_id,
        ))
        groups.setdefault(key, []).append(event)

    merged = [merge_records(records) for records in groups.values()]

    def normalized_round(value: object) -> str:
        text = re.sub(r"[\s－—_-]+", "", str(value or "")).lower().replace("轮", "")
        return "天使" if text == "angel" else text

    def normalized_amount(value: object) -> str:
        return re.sub(r"\s+", "", str(value or "")).replace("人民币", "元")

    report_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    passthrough = []
    ignored_amounts = {"", "未披露", "元", "[]"}
    for event in merged:
        company = str(event.get("company_name_standard") or event.get("company_id") or "").strip()
        round_key = normalized_round(event.get("round_original"))
        amount_key = normalized_amount(event.get("amount_original"))
        if not company or not round_key or amount_key in ignored_amounts or "/" in round_key:
            passthrough.append(event)
            continue
        report_groups.setdefault((company, round_key, amount_key), []).append(event)

    result = list(passthrough)
    for records in report_groups.values():
        clusters: list[list[dict[str, Any]]] = []
        for record in sorted(records, key=lambda row: str(row.get("disclosure_date") or "")):
            current_date = date.fromisoformat(str(record.get("disclosure_date") or record.get("announcement_date")))
            target = next((cluster for cluster in clusters if
                           abs((current_date - date.fromisoformat(str(cluster[-1].get("disclosure_date") or cluster[-1].get("announcement_date")))).days) <= 14 and
                           str(record.get("source_url") or "") != str(cluster[-1].get("source_url") or "")), None)
            if target is None:
                clusters.append([record])
            else:
                target.append(record)
        result.extend(merge_records(cluster) for cluster in clusters)
    return result


class PublicDataService:
    """Read-only facade over immutable, currently published release snapshots."""

    def __init__(self, path: Path | None = None):
        self.path = path

    def _rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        connection = connect(self.path, read_only=True)
        try:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
        finally:
            connection.close()

    def current_release(self) -> PublicRelease | None:
        rows = self._rows(
            """SELECT r.release_id,r.release_name,r.created_at,r.content_hash,
              COALESCE((SELECT h.new_status FROM release_status_history h
                        WHERE h.release_id=r.release_id ORDER BY h.changed_at DESC,h.release_status_id DESC LIMIT 1),r.status) AS current_status
              FROM releases r ORDER BY r.created_at DESC,r.release_id DESC"""
        )
        active = next((row for row in rows if row["current_status"] == "published"), None)
        if not active:
            return None
        snapshots = self._rows(
            """SELECT event_snapshot_json,evidence_snapshot_json FROM release_events
               WHERE release_id=? ORDER BY position""",
            (active["release_id"],),
        )
        events = []
        for row in snapshots:
            event = json.loads(row["event_snapshot_json"])
            evidence = json.loads(row["evidence_snapshot_json"])
            event["public_sources"] = [
                {"title": item.get("title"), "url": item.get("original_url"), "grade": item.get("evidence_grade")}
                for item in evidence
                if item.get("original_url")
            ]
            events.append(event)
        return PublicRelease(active["release_id"], active["release_name"], active["created_at"], active["content_hash"], tuple(events))

    def v30_release(self) -> dict[str, Any] | None:
        rows = self._rows("SELECT * FROM v30_releases WHERE status='published' ORDER BY created_at DESC LIMIT 1")
        return rows[0] if rows else None

    def v30_overview(self, *, include_duplicate_sources: bool = False) -> dict[str, Any] | None:
        release = self.v30_release()
        if not release: return None
        manifest = json.loads(release["manifest_json"])
        records = self._rows("SELECT event_snapshot_json,classification_snapshot_json FROM v30_release_records WHERE release_id=? ORDER BY position", (release["release_id"],))
        events = []
        for row in records:
            event = json.loads(row["event_snapshot_json"])
            event["classification"] = json.loads(row["classification_snapshot_json"])
            events.append(event)
        if not include_duplicate_sources:
            merges = self._rows("SELECT * FROM v34_candidate_source_merges WHERE decision_status='confirmed'")
            duplicate_ids = {row["duplicate_record_id"] for row in merges}
            canonical = {row["canonical_record_id"]: row for row in merges}
            events = [event for event in events if event.get("record_id") not in duplicate_ids]
            for event in events:
                decision = canonical.get(event.get("record_id"))
                if decision:
                    event["round_original"] = decision["canonical_round"]
                    event["source_merge_status"] = "confirmed"
                    event["merged_duplicate_record_id"] = decision["duplicate_record_id"]
            manifest = dict(manifest)
            manifest["historical_source_records"] = manifest.get("source_records", len(records))
            manifest["source_records"] = len(events)
            manifest["unique_candidate_events"] = len(events)
            manifest["classified"] = sum(event["classification"].get("primary_industry_id") is not None for event in events)
            manifest["pending_classification"] = len(events) - manifest["classified"]
            manifest["a_candidates"] = sum(event.get("queue_class") == "A" for event in events)
            manifest["b_candidates"] = sum(event.get("queue_class") == "B" for event in events)
        return {"release": release, "manifest": manifest, "events": events}

    def v30_taxonomy(self) -> dict[str, Any]:
        settings = self._rows(
            "SELECT taxonomy_version FROM v37_taxonomy_settings WHERE setting_key='current_taxonomy'"
        ) if self._rows("SELECT name FROM sqlite_master WHERE type='table' AND name='v37_taxonomy_settings'") else []
        if settings:
            version = settings[0]["taxonomy_version"]
            return {
                "version": version,
                "industries": self._rows(
                    "SELECT * FROM v30_industries WHERE taxonomy_version=? ORDER BY sort_order", (version,)
                ),
                "fields": self._rows(
                    "SELECT * FROM v30_fields WHERE taxonomy_version=? ORDER BY industry_id,sort_order", (version,)
                ),
                "topics": self._rows(
                    "SELECT * FROM v30_topics WHERE taxonomy_version=? ORDER BY field_id,name", (version,)
                ),
            }
        release = self.v30_release()
        if not release: return {"version": None, "industries": [], "fields": [], "topics": []}
        rows = self._rows("SELECT entity_type,snapshot_json FROM v30_release_taxonomy WHERE release_id=? ORDER BY position", (release["release_id"],))
        result = {"version": release["taxonomy_version"], "industries": [], "fields": [], "topics": []}
        names = {"industry": "industries", "field": "fields", "topic": "topics"}
        for row in rows: result[names[row["entity_type"]]].append(json.loads(row["snapshot_json"]))
        return result

    def v30_industry(self, industry_id: str) -> dict[str, Any] | None:
        taxonomy = self.v30_taxonomy(); overview = self.v30_overview()
        industry = next((x for x in taxonomy["industries"] if x["industry_id"] == industry_id), None)
        if not industry: return None
        fields = [x for x in taxonomy["fields"] if x["industry_id"] == industry_id]
        field_ids = {x["field_id"] for x in fields}
        topics = [x for x in taxonomy["topics"] if x["field_id"] in field_ids]
        return {"industry": industry, "fields": fields, "topics": topics, "events": (overview or {}).get("events", [])}

    def v30_field(self, field_id: str) -> dict[str, Any] | None:
        taxonomy = self.v30_taxonomy(); overview = self.v30_overview()
        field = next((x for x in taxonomy["fields"] if x["field_id"] == field_id), None)
        if not field: return None
        industry = next((x for x in taxonomy["industries"] if x["industry_id"] == field["industry_id"]), None)
        topics = [x for x in taxonomy["topics"] if x["field_id"] == field_id]
        return {"field": field, "industry": industry, "topics": topics, "events": (overview or {}).get("events", [])}

    def v30_topic(self, topic_id: str) -> dict[str, Any] | None:
        taxonomy = self.v30_taxonomy(); overview = self.v30_overview()
        topic = next((x for x in taxonomy["topics"] if x["topic_id"] == topic_id), None)
        if not topic: return None
        field = next(x for x in taxonomy["fields"] if x["field_id"] == topic["field_id"])
        industry = next(x for x in taxonomy["industries"] if x["industry_id"] == field["industry_id"])
        events = [x for x in (overview or {}).get("events", []) if topic_id in x["classification"].get("topic_ids", [])]
        companies = {x["company_id"]: {"company_id": x["company_id"], "name": x["company_name_standard"],
                     "business": x.get("primary_business", "待补充"), "products": x.get("core_products", "待补充"),
                     "technologies": x.get("core_technologies", "待补充")} for x in events if x.get("company_id")}
        rounds: dict[str, int] = {}
        for event in events: rounds[event["round_original"]] = rounds.get(event["round_original"], 0) + 1
        return {"topic": topic, "field": field, "industry": industry, "events": events,
                "companies": list(companies.values()), "rounds": rounds}

    def v30_company(self, company_id: str) -> dict[str, Any] | None:
        overview = self.v30_overview()
        if not overview: return None
        events = [x for x in overview["events"] if x.get("company_id") == company_id]
        if not events: return None
        first = events[0]
        return {"company_id": company_id, "name": first["company_name_standard"],
                "business": first.get("primary_business") or "待补充", "products": first.get("core_products") or "待补充",
                "technologies": first.get("core_technologies") or "待补充", "events": events}

    def _strict_formal_events(self) -> tuple[list[dict[str, Any]], str | None]:
        """Intersect explicit V1.5 confirmations with the immutable formal Release.

        The schemas intentionally have no inferred bridge. A Release snapshot must
        carry confirmed_event_id or review_item_id; ambiguous records are excluded.
        """
        release = self.current_release()
        if not release:
            return [], None
        confirmations = {row["confirmed_event_id"]: row for row in self._rows(
            "SELECT * FROM v15_confirmed_funding_events WHERE is_active=1"
        )}
        by_review = {row["review_item_id"]: row for row in confirmations.values()}
        classifications = {row["review_item_id"]: row for row in self._rows(
            """SELECT h.review_item_id,c.primary_industry_id,c.primary_field_id,c.primary_topic_id
               FROM v30_historical_records h
               JOIN v30_record_classifications c ON c.record_id=h.record_id"""
        )}
        admitted: list[dict[str, Any]] = []
        for snapshot in release.events:
            confirmed = confirmations.get(str(snapshot.get("confirmed_event_id") or ""))
            if not confirmed:
                confirmed = by_review.get(str(snapshot.get("review_item_id") or ""))
            if not confirmed:
                continue
            classification = classifications.get(confirmed["review_item_id"], {})
            currency = str(snapshot.get("amount_currency") or confirmed.get("amount_currency") or "UNKNOWN")
            exact = snapshot.get("amount_exact")
            disclosure = snapshot.get("amount_disclosure_type")
            if exact is None and currency == "CNY" and confirmed.get("amount_cny") is not None:
                exact, disclosure = confirmed["amount_cny"], "exact"
            admitted.append({
                "event_id": confirmed["confirmed_event_id"], "confirmed_event_id": confirmed["confirmed_event_id"],
                "review_item_id": confirmed["review_item_id"], "company_id": confirmed["company_id"],
                "company_name": confirmed["company_name"], "announcement_date": confirmed["disclosure_date"],
                "round_original": confirmed["round_original"], "round_normalized": confirmed["round_confirmed"],
                "amount_original": confirmed["amount_original"], "amount_currency": currency,
                "amount_exact": exact, "amount_disclosure_type": disclosure or "undisclosed",
                "is_cumulative_amount": bool(snapshot.get("is_cumulative_amount", False)),
                "primary_industry_id": classification.get("primary_industry_id"),
                "primary_field_id": classification.get("primary_field_id"),
                "primary_topic_id": classification.get("primary_topic_id"),
            })
        return admitted, release.created_at

    def formal_monthly_capital_flow(self, month: str | None = None, *, currency: str = "", industry_id: str = "", round_name: str = "") -> dict[str, Any]:
        target = month or datetime.now(CHINA_TZ).strftime("%Y-%m")
        events, updated_at = self._strict_formal_events()
        taxonomy = self.v30_taxonomy()
        return aggregate_monthly_capital_flow(events, taxonomy["industries"], target, currency=currency,
                                              industry_id=industry_id, round_name=round_name, updated_at=updated_at)

    def formal_released_events(self) -> list[dict[str, Any]]:
        events, _ = self._strict_formal_events()
        return events

    def v30_candidate_round_structure(self) -> dict[str, Any]:
        overview = self.v30_overview()
        return candidate_round_structure((overview or {}).get("events", []), self.v30_taxonomy()["industries"])

    def v30_candidate_industry_structure(self) -> dict[str, Any]:
        overview = self.v30_overview()
        taxonomy = self.v30_taxonomy()
        return candidate_industry_structure((overview or {}).get("events", []), taxonomy["industries"])

    def historical_candidate_events(self) -> list[dict[str, Any]]:
        has_v37 = bool(self._rows(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='v37_candidate_classifications'"
        ))
        v37_columns = (
            "COALESCE(v.suggested_industry_id,p.existing_industry_id) primary_industry_id,"
            "COALESCE(v.suggested_field_id,p.existing_field_id) primary_field_id,"
            "COALESCE(v.suggested_topic_id,p.existing_topic_id) primary_topic_id"
        ) if has_v37 else (
            "p.existing_industry_id primary_industry_id,p.existing_field_id primary_field_id,"
            "p.existing_topic_id primary_topic_id"
        )
        v37_join = (
            "LEFT JOIN v37_candidate_classifications v "
            "ON v.candidate_id=c.candidate_id AND v.taxonomy_version=("
            "SELECT taxonomy_version FROM v37_taxonomy_settings WHERE setting_key='current_taxonomy') "
            "AND v.review_status='pending_approval'"
        ) if has_v37 else ""
        candidates = self._rows(
            f"""SELECT c.stable_event_id unique_event_id,c.stable_event_id record_id,
                      c.company_name company_id,c.company_name company_name_standard,
                      c.announcement_date,c.announcement_date disclosure_date,c.round_original,
                      c.amount_original,c.investors_original,c.round_bucket,c.review_status,
                      c.primary_business,c.core_technology,
                      s.source_name source_platform,s.source_url,
                      {v37_columns}
               FROM v35_historical_candidates c
               LEFT JOIN v35_classification_proposals p ON p.candidate_id=c.candidate_id
               LEFT JOIN v35_candidate_sources s ON s.candidate_id=c.candidate_id
                 AND s.candidate_source_id=(
                   SELECT MIN(s2.candidate_source_id) FROM v35_candidate_sources s2
                   WHERE s2.candidate_id=c.candidate_id
                 )
               {v37_join}
               WHERE c.review_status IN ('pending','needs_verification')"""
        )
        legacy = self._rows(
            """SELECT e.cluster_id unique_event_id,e.cluster_id record_id,
                      h.company_name_standard company_id,h.company_name_standard,
                      h.disclosure_date announcement_date,h.disclosure_date,h.round_original,
                      h.amount_original,h.investors_original,h.source_platform,h.source_url,
                      h.queue_class,rc.primary_industry_id,rc.primary_field_id,rc.primary_topic_id
               FROM v35_event_clusters e
               JOIN v30_historical_records h ON h.record_id=e.canonical_record_id
               LEFT JOIN v30_record_classifications rc ON rc.record_id=h.record_id
               WHERE e.cluster_status='candidate'"""
        )
        events = candidates + legacy
        for event in events:
            event["classification"] = {
                "primary_industry_id": event.pop("primary_industry_id", None),
                "primary_field_id": event.pop("primary_field_id", None),
                "primary_topic_id": event.pop("primary_topic_id", None),
            }
        duplicate_groups: dict[str, str] = {}
        if self._rows("SELECT name FROM sqlite_master WHERE type='table' AND name='v38_historical_duplicate_reports'"):
            duplicate_rows = self._rows(
                """SELECT c1.stable_event_id canonical_event_id,c2.stable_event_id duplicate_event_id,
                          d.canonical_candidate_id group_id
                   FROM v38_historical_duplicate_reports d
                   JOIN v35_historical_candidates c1 ON c1.candidate_id=d.canonical_candidate_id
                   JOIN v35_historical_candidates c2 ON c2.candidate_id=d.duplicate_candidate_id
                   WHERE d.decision_status='confirmed'"""
            )
            for row in duplicate_rows:
                duplicate_groups[row["canonical_event_id"]] = row["group_id"]
                duplicate_groups[row["duplicate_event_id"]] = row["group_id"]
        return merge_duplicate_candidate_events(events, duplicate_groups)

    def historical_company(self, company_key: str) -> dict[str, Any] | None:
        events = [event for event in self.historical_candidate_events() if event.get("company_id") == company_key]
        if not events:
            return None
        first = events[0]
        return {
            "company_id": company_key,
            "name": first.get("company_name_standard") or company_key,
            "business": first.get("primary_business") or "主营业务待补充",
            "products": "候选层暂未结构化",
            "technologies": first.get("core_technology") or "核心技术待补充",
            "events": events,
        }

    def v30_candidate_window(self, days: int) -> dict[str, Any]:
        taxonomy = self.v30_taxonomy()
        window = rolling_window(self.historical_candidate_events(), days, cutoff="2026-11-27")
        events = window.pop("events")
        return {
            **window,
            "rounds": candidate_round_structure(events, taxonomy["industries"]),
            "industries": candidate_industry_structure(events, taxonomy["industries"]),
        }

    def formal_capital_window(self, days: int, *, cutoff: str) -> dict[str, Any]:
        events, updated_at = self._strict_formal_events()
        window = rolling_window(events, days, cutoff=cutoff)
        selected = window.pop("events")

        def valid_amount(item: dict[str, Any]) -> int | float | None:
            value = item.get("amount_exact")
            if item.get("is_cumulative_amount") or item.get("amount_disclosure_type") != "exact":
                return None
            return value if isinstance(value, (int, float)) else None

        amounts: dict[str, int | float] = {}
        for event in selected:
            value = valid_amount(event)
            currency = str(event.get("amount_currency") or "")
            if value is not None and currency:
                amounts[currency] = amounts.get(currency, 0) + value
        disclosed = [event for event in selected if valid_amount(event) is not None]
        ranged = [event for event in selected if not event.get("is_cumulative_amount") and event.get("amount_disclosure_type") in {"bounded_range", "lower_bound", "upper_bound", "order_of_magnitude"}]
        undisclosed = [event for event in selected if event.get("amount_disclosure_type") == "undisclosed"]
        return {
            **window, "updated_at": updated_at,
            "totals": {
                "event_count": len(selected), "company_count": len({event.get("company_id") for event in selected if event.get("company_id")}),
                "industry_count": len({event.get("primary_industry_id") for event in selected if event.get("primary_industry_id")}),
                "amounts": amounts, "amount_disclosed_event_count": len(disclosed),
                "range_amount_event_count": len(ranged), "undisclosed_amount_event_count": len(undisclosed),
                "usd_event_count": sum(event.get("amount_currency") == "USD" for event in selected),
            },
        }

    def v30_repeated_candidate_companies(self) -> list[dict[str, Any]]:
        overview = self.v30_overview()
        return repeated_candidate_companies((overview or {}).get("events", []))

    def v34_merged_candidate_sources(self) -> list[dict[str, Any]]:
        overview = self.v30_overview(include_duplicate_sources=True)
        by_record = {event.get("record_id"): event for event in (overview or {}).get("events", [])}
        results = []
        for decision in self._rows("SELECT * FROM v34_candidate_source_merges WHERE decision_status='confirmed' ORDER BY decided_at,merge_id"):
            canonical = by_record.get(decision["canonical_record_id"])
            duplicate = by_record.get(decision["duplicate_record_id"])
            if not canonical or not duplicate:
                continue
            canonical = dict(canonical)
            canonical["round_original"] = decision["canonical_round"]
            results.append({**decision, "company_name": canonical.get("company_name_standard") or "未命名企业",
                            "records": [canonical, duplicate]})
        return results

    def internal_monthly_quality_preview(self) -> dict[str, Any]:
        confirmed = self._rows("SELECT COUNT(*) n FROM v15_confirmed_funding_events WHERE is_active=1")[0]["n"]
        formal_events, _ = self._strict_formal_events()
        historical = self._rows("""SELECT COUNT(*) total,
          SUM(announcement_date GLOB '????-??-??') dated,
          SUM(amount_disclosure_type<>'undisclosed' AND is_cumulative_amount=0) valid_amount,
          SUM(amount_disclosure_type='exact' AND amount_exact IS NOT NULL AND is_cumulative_amount=0) exact_amount,
          SUM(amount_disclosure_type='undisclosed') undisclosed,
          SUM(is_cumulative_amount=1) cumulative FROM funding_events""")[0]
        currencies = self._rows("SELECT amount_currency,COUNT(*) event_count FROM funding_events GROUP BY amount_currency ORDER BY amount_currency")
        rounds = self._rows("SELECT round_normalized,COUNT(*) event_count FROM funding_events GROUP BY round_normalized ORDER BY event_count DESC,round_normalized")
        classified = self._rows("""SELECT COUNT(DISTINCT e.event_id) n FROM v22_events e
          JOIN v22_event_topics et ON et.event_id=e.event_id JOIN v22_topics t ON t.topic_id=et.topic_id
          JOIN v22_fields f ON f.field_id=t.field_id JOIN v22_industries i ON i.industry_id=f.industry_id
          WHERE e.event_source_type='formal'""")[0]["n"]
        raw_candidates = self._rows("SELECT queue_class,COUNT(*) event_count FROM v30_historical_records GROUP BY queue_class ORDER BY queue_class")
        candidate_overview = self.v30_overview()
        candidate_events = (candidate_overview or {}).get("events", [])
        candidate_counts = [{"queue_class": queue, "event_count": sum(event.get("queue_class") == queue for event in candidate_events)}
                            for queue in ("A", "B")]
        industry_names = {row["industry_id"]: row["name"] for row in self.v30_taxonomy()["industries"]}
        distribution: dict[tuple[str, str], int] = {}
        for event in candidate_events:
            key = (str(event.get("queue_class") or ""), industry_names.get(event["classification"].get("primary_industry_id"), "待分类"))
            distribution[key] = distribution.get(key, 0) + 1
        candidate_industries = [{"queue_class": key[0], "industry_name": key[1], "event_count": count}
                                for key, count in sorted(distribution.items(), key=lambda item: (item[0][0], -item[1], item[0][1]))]
        merge_count = self._rows("SELECT COUNT(*) n FROM v34_candidate_source_merges WHERE decision_status='confirmed'")[0]["n"]
        return {"formal": {"confirmed_events": confirmed, "released_events": len(formal_events),
                           "amount_disclosed_events": sum(1 for x in formal_events if x.get("amount_disclosure_type") == "exact" and not x.get("is_cumulative_amount")),
                           "classified_events": sum(1 for x in formal_events if x.get("primary_industry_id"))},
                "historical": {**historical, "classified_events": classified, "currencies": currencies, "rounds": rounds},
                "candidates": {"counts": candidate_counts, "industries": candidate_industries,
                               "raw_counts": raw_candidates, "raw_source_records": sum(row["event_count"] for row in raw_candidates),
                               "effective_events": len(candidate_events), "merged_duplicate_sources": merge_count}}

    def overview(self) -> dict[str, Any]:
        release = self.current_release()
        if not release:
            return {"release": None, "events": (), "metrics": None}
        events = release.events
        exact = [e for e in events if e.get("amount_disclosure_type") == "exact" and not e.get("is_cumulative_amount") and e.get("amount_exact") is not None]
        metrics = {
            "events": len({e["event_id"] for e in events}),
            "exact_amount": sum(int(e["amount_exact"]) for e in exact),
            "companies": len({e["company_id"] for e in events}),
            "investors": len({i["investor_id"] for e in events for i in e.get("investors", [])}),
        }
        return {"release": release, "events": events, "metrics": metrics}

    def monthly_analysis(self, filters: PublicFilters | None = None) -> dict[str, Any]:
        filters = filters or PublicFilters()
        release = self.current_release()
        empty = {"release": None, "months": [], "investors": [], "events": [], "tracks": [], "years": [], "rounds": [], "total_events": 0, "page": 1, "pages": 0, "coverage": None}
        if not release:
            return empty

        unique: dict[str, dict[str, Any]] = {}
        for raw in release.events:
            event_id = str(raw.get("event_id") or "")
            if not event_id or event_id in unique:
                continue
            event = dict(raw)
            event["month"] = china_month(event.get("announcement_date"))
            event["track_id"], event["track_name"] = primary_track(event)
            event["investors"] = list({str(i.get("investor_id")): i for i in event.get("investors", []) if i.get("investor_id")}.values())
            unique[event_id] = event
        all_events = list(unique.values())
        dated = [event for event in all_events if event["month"]]
        tracks = sorted({(event["track_id"], event["track_name"]) for event in dated}, key=lambda item: item[1])
        years = sorted({event["month"][:4] for event in dated}, reverse=True)
        rounds = sorted({str(event.get("round_normalized")) for event in dated if event.get("round_normalized")})

        def matches(event: dict[str, Any], *, include_month: bool = True) -> bool:
            if not event["month"]:
                return False
            if include_month and filters.month and event["month"] != filters.month:
                return False
            if filters.track_id and event["track_id"] != filters.track_id:
                return False
            if filters.year and not event["month"].startswith(filters.year + "-"):
                return False
            if filters.round_name and str(event.get("round_normalized") or "") != filters.round_name:
                return False
            if filters.company and filters.company.casefold() not in str(event.get("company_name") or "").casefold():
                return False
            if filters.investor:
                needle = filters.investor.casefold()
                if not any(needle in str(item.get("official_name") or "").casefold() for item in event["investors"]):
                    return False
            return True

        chart_events = [event for event in all_events if matches(event, include_month=False)]
        selected_events = [event for event in all_events if matches(event)]
        month_map: dict[str, dict[str, int]] = {}
        track_names = dict(tracks)
        for event in chart_events:
            counts = month_map.setdefault(event["month"], {})
            counts[event["track_id"]] = counts.get(event["track_id"], 0) + 1
        months = [
            {"month": month, "tracks": [{"track_id": track_id, "track_name": track_names.get(track_id, "未分类"), "event_count": count} for track_id, count in sorted(counts.items())], "total_event_count": sum(counts.values())}
            for month, counts in sorted(month_map.items())
        ]

        investor_events: dict[str, set[str]] = {}
        investor_names: dict[str, str] = {}
        for event in selected_events:
            for investor in event["investors"]:
                investor_id = str(investor["investor_id"])
                investor_events.setdefault(investor_id, set()).add(str(event["event_id"]))
                investor_names[investor_id] = str(investor.get("official_name") or investor_id)
        investors = sorted(
            ({"investor_id": key, "investor_name": investor_names[key], "investor_event_count": len(value)} for key, value in investor_events.items()),
            key=lambda item: (-item["investor_event_count"], item["investor_name"]),
        )[:10]

        selected_events.sort(key=lambda item: (item.get("announcement_date") or "", item.get("event_id") or ""), reverse=True)
        total = len(selected_events)
        page_size = min(max(filters.page_size, 1), 50)
        pages = (total + page_size - 1) // page_size
        page_number = min(max(filters.page, 1), max(pages, 1))
        start = (page_number - 1) * page_size
        coverage_months = sorted({event["month"] for event in dated})
        return {
            "release": release,
            "months": months,
            "investors": investors,
            "events": selected_events[start:start + page_size],
            "tracks": [{"track_id": key, "track_name": name} for key, name in tracks],
            "years": years,
            "rounds": rounds,
            "total_events": total,
            "page": page_number,
            "pages": pages,
            "coverage": {"first_month": coverage_months[0], "last_month": coverage_months[-1], "complete": False} if coverage_months else None,
        }

    def search(self, query: str) -> list[dict[str, str]]:
        release = self.current_release()
        if not release or not query.strip():
            return []
        needle = query.casefold()
        results = []
        for event in release.events:
            track = primary_track(event)[1]
            investors = " ".join(str(item.get("official_name") or "") for item in event.get("investors", []))
            haystack = " ".join(str(event.get(k) or "") for k in ("company_name", "round_original", "use_of_funds_original")) + f" {track} {investors}"
            if needle in haystack.casefold():
                results.append({"type": "融资事件", "title": event.get("company_name") or "未命名企业", "url": f"/events/{event['event_id']}"})
        return results

    def event(self, event_id: str) -> dict[str, Any] | None:
        release = self.current_release()
        if not release:
            return None
        return next((event for event in release.events if event.get("event_id") == event_id), None)

    def company(self, company_id: str) -> dict[str, Any] | None:
        release = self.current_release()
        if not release:
            return None
        matches = [event for event in release.events if event.get("company_id") == company_id]
        return {"company_id": company_id, "name": matches[0].get("company_name"), "events": matches} if matches else None
