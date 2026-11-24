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
