from __future__ import annotations

import hashlib
import json
from pathlib import Path

from funding_radar.db import connect
from funding_radar.repository import LedgerRepository, now, uid


PUBLISH_FIELDS = ("company_id", "announcement_date")


def quality_issues(path: Path | None = None) -> list[str]:
    repo = LedgerRepository(path)
    issues = []
    high = repo.rows("SELECT COUNT(*) AS n FROM dedup_candidates WHERE status='pending' AND risk_level='high'")[0]["n"]
    if high:
        issues.append(f"存在 {high} 个未解决的高风险重复候选")
    candidates = repo.rows("SELECT * FROM funding_events WHERE review_status='approved' ORDER BY event_id")
    if not candidates:
        issues.append("没有已批准事件")
    for event in candidates:
        company = repo.rows("SELECT human_review_status FROM companies WHERE company_id=?", (event["company_id"],))[0]
        if company["human_review_status"] != "confirmed":
            issues.append(f"事件 {event['event_id']} 的企业主体未确认")
        if not event["announcement_date"]:
            issues.append(f"事件 {event['event_id']} 缺少已确认日期")
        if event["evidence_grade"] not in {"S", "A", "B"}:
            issues.append(f"事件 {event['event_id']} 只有 {event['evidence_grade']} 级证据")
        fields = {r["field_name"] for r in repo.evidence_for_event(event["event_id"]) if r["verification_status"] == "verified"}
        for required in {"company_id", "financing_fact", "announcement_date"}:
            if required not in fields:
                issues.append(f"事件 {event['event_id']} 缺少字段证据：{required}")
    return issues


def create_release(name: str, actor: str, path: Path | None = None) -> str:
    issues = quality_issues(path)
    if issues:
        raise ValueError("; ".join(issues))
    repo = LedgerRepository(path)
    events = repo.rows("SELECT e.*, c.official_name AS company_name FROM funding_events e JOIN companies c USING(company_id) WHERE e.review_status='approved' ORDER BY e.event_id")
    snapshots = []
    for event in events:
        investors = repo.rows(
            """SELECT i.investor_id,i.official_name,ei.role,ei.role_original
               FROM event_investors ei JOIN investors i USING(investor_id)
               WHERE ei.event_id=? ORDER BY i.official_name""",
            (event["event_id"],),
        )
        event["investors"] = investors
        evidence = repo.evidence_for_event(event["event_id"])
        snapshots.append((event, evidence))
    canonical = json.dumps(snapshots, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode()).hexdigest()
    release_id = uid()
    manifest = {"schema_version": 2, "event_ids": [e[0]["event_id"] for e in snapshots], "content_hash": content_hash}
    connection = connect(path)
    try:
        with connection:
            connection.execute("INSERT INTO releases VALUES (?,?,?,?,?,?,?,?)", (release_id, name, actor, now(), json.dumps(manifest, sort_keys=True), len(events), content_hash, "published"))
            for position, (event, evidence) in enumerate(snapshots, 1):
                connection.execute("INSERT INTO release_events VALUES (?,?,?,?,?)", (release_id, event["event_id"], json.dumps(event, ensure_ascii=False, sort_keys=True), json.dumps(evidence, ensure_ascii=False, sort_keys=True), position))
            audit_id = uid()
            connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)", (audit_id,actor,"create_release","release",release_id,None,json.dumps({"status":"published"}),"quality gates passed",None,now()))
            connection.execute("INSERT INTO release_status_history VALUES (?,?,?,?,?,?,?,?)", (uid(),release_id,None,"published",actor,"initial publication",now(),audit_id))
    finally:
        connection.close()
    return release_id


def decide_dedup(candidate_id: str, decision: str, reason: str, actor: str, rule_version_id: str, path: Path | None = None) -> str:
    repo = LedgerRepository(path)
    current = repo.rows("SELECT * FROM dedup_decisions WHERE candidate_id=? AND is_current=1", (candidate_id,))
    connection = connect(path)
    decision_id = uid()
    try:
        with connection:
            if current:
                connection.execute("UPDATE dedup_decisions SET is_current=0 WHERE decision_id=?", (current[0]["decision_id"],))
            connection.execute("INSERT INTO dedup_decisions VALUES (?,?,?,?,?,?,?,?,?)", (decision_id, candidate_id, decision, reason, actor, now(), rule_version_id, 1, current[0]["decision_id"] if current else None))
            connection.execute("UPDATE dedup_candidates SET status=? WHERE candidate_id=?", ("pending" if decision == "pending" else "resolved", candidate_id))
    finally:
        connection.close()
    repo.audit(actor, "dedup_decision", "dedup_candidate", candidate_id, current[0] if current else None, {"decision": decision, "decision_id": decision_id}, reason, rule_version_id)
    return decision_id

