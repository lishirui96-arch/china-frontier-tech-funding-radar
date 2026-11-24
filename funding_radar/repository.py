from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from funding_radar.db import connect


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid() -> str:
    return str(uuid.uuid4())


class LedgerRepository:
    def __init__(self, path: Path | None = None, *, read_only: bool = False):
        self.path = path
        self.read_only = read_only

    def rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        connection = connect(self.path, read_only=self.read_only)
        try:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
        finally:
            connection.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        if self.read_only:
            raise RuntimeError("Repository is read-only")
        connection = connect(self.path)
        try:
            with connection:
                connection.execute(sql, params)
        finally:
            connection.close()

    def audit(self, actor: str, action: str, entity_type: str, entity_id: str, before: Any, after: Any, reason: str, rule_version_id: str | None = None) -> None:
        self.execute(
            "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid(), actor, action, entity_type, entity_id, json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None, json.dumps(after, ensure_ascii=False, sort_keys=True) if after is not None else None, reason, rule_version_id, now()),
        )

    def update_document_review(self, document_id: str, relevance: str, actor: str, reason: str) -> None:
        before = self.rows("SELECT relevance_status, review_status FROM raw_documents WHERE document_id=?", (document_id,))[0]
        review = "parsed" if relevance in {"relevant", "uncertain"} else "rejected"
        self.execute("UPDATE raw_documents SET relevance_status=?, review_status=? WHERE document_id=?", (relevance, review, document_id))
        self.audit(actor, "review_document", "raw_document", document_id, before, {"relevance_status": relevance, "review_status": review}, reason)

    def list_documents(self) -> list[dict[str, Any]]:
        return self.rows("SELECT d.*, s.name AS source_name, s.evidence_default_grade FROM raw_documents d JOIN sources s USING(source_id) ORDER BY COALESCE(published_at,fetched_at) DESC")

    def list_entities(self, kind: str) -> list[dict[str, Any]]:
        if kind not in {"companies", "investors"}:
            raise ValueError(kind)
        return self.rows(f"SELECT * FROM {kind} ORDER BY official_name")

    def list_aliases(self, kind: str) -> list[dict[str, Any]]:
        if kind == "companies":
            return self.rows("SELECT a.*, c.official_name FROM company_aliases a JOIN companies c USING(company_id) ORDER BY alias")
        if kind == "investors":
            return self.rows("SELECT a.*, i.official_name FROM investor_aliases a JOIN investors i USING(investor_id) ORDER BY alias")
        raise ValueError(kind)

    def list_events(self, release_id: str | None = None) -> list[dict[str, Any]]:
        if release_id:
            return self.rows("SELECT event_snapshot_json FROM release_events WHERE release_id=? ORDER BY position", (release_id,))
        return self.rows("SELECT e.*, c.official_name AS company_name FROM funding_events e JOIN companies c USING(company_id) ORDER BY announcement_date DESC")

    def list_dedup_candidates(self) -> list[dict[str, Any]]:
        return self.rows("""SELECT d.*, lc.official_name AS left_company, rc.official_name AS right_company,
            le.announcement_date AS left_date, re.announcement_date AS right_date,
            le.round_original AS left_round, re.round_original AS right_round,
            le.amount_original AS left_amount, re.amount_original AS right_amount
            FROM dedup_candidates d JOIN funding_events le ON le.event_id=d.left_event_id
            JOIN funding_events re ON re.event_id=d.right_event_id
            JOIN companies lc ON lc.company_id=le.company_id JOIN companies rc ON rc.company_id=re.company_id
            ORDER BY CASE d.risk_level WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, d.total_score DESC""")

    def evidence_for_event(self, event_id: str) -> list[dict[str, Any]]:
        return self.rows("SELECT e.*, d.title, d.original_url FROM evidence_records e JOIN raw_documents d USING(document_id) WHERE e.entity_type='funding_event' AND e.entity_id=? ORDER BY field_name", (event_id,))

    def releases(self) -> list[dict[str, Any]]:
        return self.rows("SELECT * FROM releases ORDER BY created_at DESC")

