from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from funding_radar.db import connect


@dataclass(frozen=True)
class PublicRelease:
    release_id: str
    release_name: str
    created_at: str
    content_hash: str
    events: tuple[dict[str, Any], ...]


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
                        WHERE h.release_id=r.release_id ORDER BY h.changed_at DESC LIMIT 1),r.status) AS current_status
              FROM releases r ORDER BY r.created_at DESC"""
        )
        active = next((row for row in rows if row["current_status"] == "published"), None)
        if not active:
            return None
        snapshots = self._rows(
            "SELECT event_snapshot_json FROM release_events WHERE release_id=? ORDER BY position",
            (active["release_id"],),
        )
        events = tuple(json.loads(row["event_snapshot_json"]) for row in snapshots)
        return PublicRelease(active["release_id"], active["release_name"], active["created_at"], active["content_hash"], events)

    def overview(self, period_days: int = 90) -> dict[str, Any]:
        release = self.current_release()
        if not release:
            return {"release": None, "period_days": period_days, "events": (), "metrics": None}
        events = release.events
        exact = [e for e in events if e.get("amount_disclosure_type") == "exact" and not e.get("is_cumulative_amount") and e.get("amount_exact") is not None]
        metrics = {
            "events": len({e["event_id"] for e in events}),
            "exact_amount": sum(int(e["amount_exact"]) for e in exact),
            "companies": len({e["company_id"] for e in events}),
            "investors": len({i["investor_id"] for e in events for i in e.get("investors", [])}),
        }
        return {"release": release, "period_days": period_days, "events": events, "metrics": metrics}

    def search(self, query: str) -> list[dict[str, str]]:
        release = self.current_release()
        if not release or not query.strip():
            return []
        needle = query.casefold()
        results = []
        for event in release.events:
            haystack = " ".join(str(event.get(k) or "") for k in ("company_name", "round_original", "use_of_funds_original"))
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

