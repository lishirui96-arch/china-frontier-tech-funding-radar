from __future__ import annotations

import json
from pathlib import Path

from funding_radar.db import connect
from funding_radar.repository import LedgerRepository, now, uid


def confirm_entity(kind: str, entity_id: str, actor: str, reason: str, path: Path | None = None) -> None:
    table, key = ("companies","company_id") if kind == "company" else ("investors","investor_id")
    repo = LedgerRepository(path)
    before = repo.rows(f"SELECT * FROM {table} WHERE {key}=?", (entity_id,))[0]
    repo.execute(f"UPDATE {table} SET normalization_status='confirmed',human_review_status='confirmed',updated_at=? WHERE {key}=?", (now(),entity_id))
    repo.audit(actor,"confirm_entity",kind,entity_id,before,{**before,"normalization_status":"confirmed","human_review_status":"confirmed"},reason)


def update_event_fields(event_id: str, changes: dict, actor: str, reason: str, path: Path | None = None) -> None:
    allowed = {"round_original","round_normalized","amount_original","amount_exact","amount_min","amount_max","amount_currency","amount_disclosure_type","is_cumulative_amount","use_of_funds_original","review_status"}
    if not changes or not set(changes).issubset(allowed):
        raise ValueError("Unsupported event fields")
    if changes.get("amount_disclosure_type") != "exact" and changes.get("amount_exact") is not None:
        raise ValueError("Only exact disclosure may set amount_exact")
    if changes.get("is_cumulative_amount") and changes.get("amount_exact") is not None:
        raise ValueError("Cumulative amount cannot be a round exact amount")
    repo = LedgerRepository(path)
    before = repo.rows("SELECT * FROM funding_events WHERE event_id=?", (event_id,))[0]
    sql = ",".join(f"{key}=?" for key in changes) + ",updated_at=?"
    repo.execute(f"UPDATE funding_events SET {sql} WHERE event_id=?", tuple(changes.values())+(now(),event_id))
    repo.audit(actor,"update_event_fields","funding_event",event_id,before,{**before,**changes},reason)


def record_review(entity_type: str, entity_id: str, round_number: int, reviewer: str, result: str, findings: dict, reason: str, path: Path | None = None) -> str:
    review_id = uid()
    connection = connect(path)
    try:
        with connection:
            connection.execute("INSERT INTO review_rounds VALUES (?,?,?,?,?,?,?,?,?)", (review_id,entity_type,entity_id,round_number,reviewer,result,json.dumps(findings,ensure_ascii=False,sort_keys=True),reason,now()))
    finally:
        connection.close()
    LedgerRepository(path).audit(reviewer,"record_review_round",entity_type,entity_id,None,{"round":round_number,"result":result,"findings":findings},reason)
    return review_id


def add_evidence(document_id: str, entity_type: str, entity_id: str, field_name: str, excerpt: str, span_start: int, grade: str, actor: str, reason: str, path: Path | None = None) -> str:
    evidence_id = uid()
    connection = connect(path)
    try:
        with connection:
            connection.execute("INSERT INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (evidence_id,document_id,entity_type,entity_id,field_name,excerpt,span_start,span_start+len(excerpt),grade,"verified",actor,now(),now()))
    finally:
        connection.close()
    LedgerRepository(path).audit(actor,"add_evidence",entity_type,entity_id,None,{"evidence_id":evidence_id,"field":field_name},reason)
    return evidence_id


def change_release_status(release_id: str, new_status: str, actor: str, reason: str, path: Path | None = None) -> str:
    repo = LedgerRepository(path)
    history = repo.rows("SELECT new_status FROM release_status_history WHERE release_id=? ORDER BY changed_at DESC LIMIT 1", (release_id,))
    release = repo.rows("SELECT status FROM releases WHERE release_id=?", (release_id,))
    old = history[0]["new_status"] if history else release[0]["status"]
    audit_id, status_id = uid(), uid()
    connection = connect(path)
    try:
        with connection:
            connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (audit_id,actor,"change_release_status","release",release_id,json.dumps({"status":old}),json.dumps({"status":new_status}),reason,None,now()))
            connection.execute("INSERT INTO release_status_history VALUES (?,?,?,?,?,?,?,?)", (status_id,release_id,old,new_status,actor,reason,now(),audit_id))
    finally:
        connection.close()
    return status_id
