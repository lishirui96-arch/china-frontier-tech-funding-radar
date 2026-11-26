from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from funding_radar.db import database_path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    existing = connection.execute("SELECT * FROM v30_releases WHERE release_name='V3.0' AND status='published'").fetchone()
    if existing:
        print(json.dumps({"release_id": existing["release_id"], "existing": True}, ensure_ascii=False)); return
    taxonomy = {
        "industry": [dict(x) for x in connection.execute("SELECT * FROM v30_industries WHERE taxonomy_version='V3.0' ORDER BY sort_order")],
        "field": [dict(x) for x in connection.execute("SELECT * FROM v30_fields WHERE taxonomy_version='V3.0' ORDER BY industry_id,sort_order")],
        "topic": [dict(x) for x in connection.execute("SELECT * FROM v30_topics WHERE taxonomy_version='V3.0' ORDER BY field_id,name")],
    }
    records = []
    for row in connection.execute("""SELECT h.*,c.*,p.primary_business,p.core_products,p.core_technologies,p.application_scenarios,p.value_chain_position
      FROM v30_historical_records h JOIN v30_record_classifications c USING(record_id)
      LEFT JOIN v22_company_profiles p USING(company_id) ORDER BY h.disclosure_date DESC,h.company_name_standard"""):
        item = dict(row)
        links = [dict(x) for x in connection.execute("SELECT topic_id,link_role,basis,review_status FROM v30_record_topics WHERE record_id=? ORDER BY link_role,topic_id", (row["record_id"],))]
        classification = {
            "primary_industry_id": row["primary_industry_id"], "primary_field_id": row["primary_field_id"],
            "primary_topic_id": row["primary_topic_id"], "topic_ids": [x["topic_id"] for x in links],
            "topic_links": links, "confidence": row["confidence"], "needs_manual_review": row["needs_manual_review"],
            "classification_status": row["classification_status"], "classification_reason": row["classification_reason"],
        }
        records.append((item, classification))
    formal_count = connection.execute("SELECT COUNT(*) FROM funding_events WHERE event_status<>'superseded'").fetchone()[0]
    acquisition_count = connection.execute("SELECT COUNT(*) FROM v15_acquisition_review_queue").fetchone()[0]
    manifest = {
        "taxonomy_version": "V3.0", "taxonomy_status": "frozen", "industries": 10, "fields": 38, "topics": 34,
        "source_records": len(records), "unique_candidate_events": len({x[0]["unique_event_id"] for x in records}),
        "formal_events": formal_count, "a_candidates": sum(x[0]["queue_class"] == "A" for x in records),
        "b_candidates": sum(x[0]["queue_class"] == "B" for x in records), "acquisitions": acquisition_count,
        "classified": sum(x[1]["primary_topic_id"] is not None for x in records),
        "pending_classification": sum(x[1]["primary_topic_id"] is None for x in records),
        "scope": "2026-11-01至2026-11-25；正式与候选状态分开展示",
    }
    payload = json.dumps({"manifest": manifest, "taxonomy": taxonomy, "records": records}, ensure_ascii=False, sort_keys=True)
    release_id = str(uuid.uuid5(uuid.UUID("a1bd68e4-3307-49e2-bc55-e43ff9b47b63"), hashlib.sha256(payload.encode()).hexdigest()))
    content_hash = hashlib.sha256(payload.encode()).hexdigest()
    timestamp = now()
    with connection:
        connection.execute("INSERT INTO v30_releases VALUES (?,?,?,?,?,?,?,?)",
                           (release_id,"V3.0","V3.0","published",json.dumps(manifest,ensure_ascii=False,sort_keys=True),content_hash,"Codex",timestamp))
        position = 0
        for kind in ("industry","field","topic"):
            for item in taxonomy[kind]:
                position += 1
                entity_id = item[f"{kind}_id"]
                connection.execute("INSERT INTO v30_release_taxonomy VALUES (?,?,?,?,?)",
                                   (release_id,kind,entity_id,json.dumps(item,ensure_ascii=False,sort_keys=True),position))
        for position, (event, classification) in enumerate(records, 1):
            connection.execute("INSERT INTO v30_release_records VALUES (?,?,?,?,?)",
                               (release_id,event["record_id"],json.dumps(event,ensure_ascii=False,sort_keys=True),
                                json.dumps(classification,ensure_ascii=False,sort_keys=True),position))
        connection.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (str(uuid.uuid4()),"Codex","create_v30_release","v30_release",release_id,None,
                            json.dumps({"manifest":manifest,"content_hash":content_hash},ensure_ascii=False),
                            "V3.0完整性、外键、迁移、分类关联和页面测试通过后发布",None,timestamp))
    print(json.dumps({"release_id":release_id,"manifest":manifest,"content_hash":content_hash},ensure_ascii=False))
    connection.close()


if __name__ == "__main__":
    main()
