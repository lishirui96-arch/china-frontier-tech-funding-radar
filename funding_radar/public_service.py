from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
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

    def v30_overview(self) -> dict[str, Any] | None:
        release = self.v30_release()
        if not release: return None
        manifest = json.loads(release["manifest_json"])
        records = self._rows("SELECT event_snapshot_json,classification_snapshot_json FROM v30_release_records WHERE release_id=? ORDER BY position", (release["release_id"],))
        events = []
        for row in records:
            event = json.loads(row["event_snapshot_json"])
            event["classification"] = json.loads(row["classification_snapshot_json"])
            events.append(event)
        return {"release": release, "manifest": manifest, "events": events}

    def v30_taxonomy(self) -> dict[str, list[dict[str, Any]]]:
        release = self.v30_release()
        if not release: return {"industries": [], "fields": [], "topics": []}
        rows = self._rows("SELECT entity_type,snapshot_json FROM v30_release_taxonomy WHERE release_id=? ORDER BY position", (release["release_id"],))
        result = {"industries": [], "fields": [], "topics": []}
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
        candidates = self._rows("SELECT queue_class,COUNT(*) event_count FROM v30_historical_records GROUP BY queue_class ORDER BY queue_class")
        candidate_industries = self._rows("""SELECT h.queue_class,i.name industry_name,COUNT(DISTINCT h.record_id) event_count
          FROM v30_historical_records h JOIN v30_record_classifications c ON c.record_id=h.record_id
          LEFT JOIN v22_industries i ON i.industry_id=c.primary_industry_id
          GROUP BY h.queue_class,i.name ORDER BY h.queue_class,event_count DESC""")
        return {"formal": {"confirmed_events": confirmed, "released_events": len(formal_events),
                           "amount_disclosed_events": sum(1 for x in formal_events if x.get("amount_disclosure_type") == "exact" and not x.get("is_cumulative_amount")),
                           "classified_events": sum(1 for x in formal_events if x.get("primary_industry_id"))},
                "historical": {**historical, "classified_events": classified, "currencies": currencies, "rounds": rounds},
                "candidates": {"counts": candidates, "industries": candidate_industries}}

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
