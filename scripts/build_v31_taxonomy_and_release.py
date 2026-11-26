from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from funding_radar.db import database_path


VERSION = "V3.1"
NS = uuid.UUID("dfd5e2bf-e49f-4f4b-98e8-0b44472b6b89")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(kind: str, value: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{value}"))


def main() -> None:
    db = sqlite3.connect(database_path())
    db.row_factory = sqlite3.Row
    timestamp = now()
    with db:
        exists = db.execute("SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version=?", (VERSION,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO v30_taxonomy_versions VALUES (?,?,?,?,?,?,?,?)",
                (VERSION, "draft", 17, "468e7bd5e53d8e419284f2ad9e2a9aa7d68ad3e9", "Codex", timestamp, None,
                 "V3.0分类骨架加21条来源复核形成的3个二级领域和16个三级主题"),
            )
            db.execute(
                """INSERT INTO v30_industries
                SELECT ?,industry_id,code,name,sort_order,source_industry_id FROM v30_industries WHERE taxonomy_version='V3.0'""",
                (VERSION,),
            )
            db.execute(
                """INSERT INTO v30_fields
                SELECT ?,field_id,industry_id,name,sort_order,source_field_id FROM v30_fields WHERE taxonomy_version='V3.0'""",
                (VERSION,),
            )
            db.execute(
                """INSERT INTO v30_topics
                SELECT ?,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
                FROM v30_topics WHERE taxonomy_version='V3.0'""",
                (VERSION,),
            )
            db.execute(
                """INSERT INTO v30_topic_aliases
                SELECT ?,alias_topic_id,canonical_topic_id,relation_type,reason,review_status
                FROM v30_topic_aliases WHERE taxonomy_version='V3.0'""",
                (VERSION,),
            )

            for proposal in db.execute("SELECT * FROM v31_taxonomy_extension_proposals ORDER BY proposed_field_name"):
                industry = db.execute(
                    "SELECT industry_id FROM v30_industries WHERE taxonomy_version=? AND name=?",
                    (VERSION, proposal["parent_industry_name"]),
                ).fetchone()
                max_order = db.execute(
                    "SELECT COALESCE(MAX(sort_order),0) FROM v30_fields WHERE taxonomy_version=? AND industry_id=?",
                    (VERSION, industry["industry_id"]),
                ).fetchone()[0]
                field_id = uid("field", proposal["proposed_field_name"])
                db.execute(
                    "INSERT INTO v30_fields VALUES (?,?,?,?,?,?)",
                    (VERSION, field_id, industry["industry_id"], proposal["proposed_field_name"], max_order + 1,
                     f'v31-proposal:{proposal["proposal_id"]}'),
                )

            reviews = [dict(row) for row in db.execute("SELECT * FROM v31_pending_classification_reviews")]
            for review in reviews:
                topic_name = review["proposed_topic_name"]
                if not topic_name:
                    continue
                field = db.execute(
                    """SELECT f.field_id FROM v30_fields f JOIN v30_industries i
                       ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id
                       WHERE f.taxonomy_version=? AND i.name=? AND f.name=?""",
                    (VERSION, review["proposed_industry_name"], review["proposed_field_name"]),
                ).fetchone()
                existing_topic = db.execute(
                    "SELECT topic_id FROM v30_topics WHERE taxonomy_version=? AND field_id=? AND name=?",
                    (VERSION, field["field_id"], topic_name),
                ).fetchone()
                if not existing_topic:
                    topic_id = uid("topic", topic_name)
                    db.execute(
                        "INSERT INTO v30_topics VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (VERSION, topic_id, field["field_id"], topic_name, review["classification_basis"],
                         "candidate", "source_reviewed", "v31_pending21_review", review["review_id"],
                         topic_name.casefold()),
                    )

            db.execute("UPDATE v30_record_classifications SET taxonomy_version=?,updated_at=?,updated_by=?",
                       (VERSION, timestamp, "codex_v31_sync"))
            for review in reviews:
                if not review["proposed_industry_name"]:
                    db.execute(
                        """UPDATE v30_record_classifications SET primary_industry_id=NULL,primary_field_id=NULL,
                           primary_topic_id=NULL,classification_reason=?,confidence='unclassified',needs_manual_review=1,
                           classification_status='pending_manual_classification',updated_at=?,updated_by=? WHERE record_id=?""",
                        (review["classification_basis"], timestamp, "codex_v31_sync", review["record_id"]),
                    )
                    db.execute("DELETE FROM v30_record_topics WHERE record_id=?", (review["record_id"],))
                    continue
                industry = db.execute(
                    "SELECT industry_id FROM v30_industries WHERE taxonomy_version=? AND name=?",
                    (VERSION, review["proposed_industry_name"]),
                ).fetchone()
                field = db.execute(
                    "SELECT field_id FROM v30_fields WHERE taxonomy_version=? AND industry_id=? AND name=?",
                    (VERSION, industry["industry_id"], review["proposed_field_name"]),
                ).fetchone()
                topic = None
                if review["proposed_topic_name"]:
                    topic = db.execute(
                        "SELECT topic_id FROM v30_topics WHERE taxonomy_version=? AND field_id=? AND name=?",
                        (VERSION, field["field_id"], review["proposed_topic_name"]),
                    ).fetchone()
                db.execute(
                    """UPDATE v30_record_classifications SET primary_industry_id=?,primary_field_id=?,primary_topic_id=?,
                       classification_reason=?,confidence=?,needs_manual_review=1,classification_status='classified_proposed',
                       updated_at=?,updated_by=? WHERE record_id=?""",
                    (industry["industry_id"], field["field_id"], topic["topic_id"] if topic else None,
                     review["classification_basis"], review["classification_confidence"], timestamp,
                     "codex_v31_sync", review["record_id"]),
                )
                db.execute("DELETE FROM v30_record_topics WHERE record_id=?", (review["record_id"],))
                if topic:
                    db.execute(
                        "INSERT INTO v30_record_topics VALUES (?,?,?,?,?,?)",
                        (review["record_id"], VERSION, topic["topic_id"], "primary", review["classification_basis"], "proposed"),
                    )
            db.execute("UPDATE v30_taxonomy_versions SET status='frozen',frozen_at=? WHERE taxonomy_version=?", (timestamp, VERSION))

        existing_release = db.execute("SELECT release_id FROM v30_releases WHERE release_name=?", (VERSION,)).fetchone()
        if existing_release:
            print(json.dumps({"release_id": existing_release["release_id"], "existing": True}, ensure_ascii=False))
            return

        taxonomy = {
            "industry": [dict(x) for x in db.execute("SELECT * FROM v30_industries WHERE taxonomy_version=? ORDER BY sort_order", (VERSION,))],
            "field": [dict(x) for x in db.execute("SELECT * FROM v30_fields WHERE taxonomy_version=? ORDER BY industry_id,sort_order", (VERSION,))],
            "topic": [dict(x) for x in db.execute("SELECT * FROM v30_topics WHERE taxonomy_version=? ORDER BY field_id,name", (VERSION,))],
        }
        review_by_record = {x["record_id"]: dict(x) for x in db.execute("SELECT * FROM v31_pending_classification_reviews")}
        records = []
        for row in db.execute(
            """SELECT h.*,c.*,p.primary_business,p.core_products,p.core_technologies,p.application_scenarios,p.value_chain_position
               FROM v30_historical_records h JOIN v30_record_classifications c USING(record_id)
               LEFT JOIN v22_company_profiles p USING(company_id)
               WHERE c.taxonomy_version=? ORDER BY h.disclosure_date DESC,h.company_name_standard""",
            (VERSION,),
        ):
            item = dict(row)
            review = review_by_record.get(row["record_id"])
            if review:
                item["primary_business"] = review["business_summary"]
                item["core_products"] = review["product_summary"]
                item["core_technologies"] = review["technology_summary"]
            links = [dict(x) for x in db.execute(
                "SELECT topic_id,link_role,basis,review_status FROM v30_record_topics WHERE record_id=? ORDER BY link_role,topic_id",
                (row["record_id"],),
            )]
            classification = {
                "primary_industry_id": row["primary_industry_id"], "primary_field_id": row["primary_field_id"],
                "primary_topic_id": row["primary_topic_id"], "topic_ids": [x["topic_id"] for x in links],
                "topic_links": links, "confidence": row["confidence"], "needs_manual_review": row["needs_manual_review"],
                "classification_status": row["classification_status"], "classification_reason": row["classification_reason"],
            }
            records.append((item, classification))

        formal_count = db.execute("SELECT COUNT(*) FROM funding_events WHERE event_status<>'superseded'").fetchone()[0]
        acquisition_count = db.execute("SELECT COUNT(*) FROM v15_acquisition_review_queue").fetchone()[0]
        classified = sum(x[1]["primary_industry_id"] is not None for x in records)
        manifest = {
            "taxonomy_version": VERSION, "taxonomy_status": "frozen", "industries": len(taxonomy["industry"]),
            "fields": len(taxonomy["field"]), "topics": len(taxonomy["topic"]), "source_records": len(records),
            "unique_candidate_events": len({x[0]["unique_event_id"] for x in records}), "formal_events": formal_count,
            "a_candidates": sum(x[0]["queue_class"] == "A" for x in records),
            "b_candidates": sum(x[0]["queue_class"] == "B" for x in records), "acquisitions": acquisition_count,
            "classified": classified, "pending_classification": len(records) - classified,
            "scope": "2026-11-01至2026-11-25；正式与候选状态分开展示",
        }
        payload = json.dumps({"manifest": manifest, "taxonomy": taxonomy, "records": records}, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(payload.encode()).hexdigest()
        release_id = uid("release", content_hash)
        db.execute("INSERT INTO v30_releases VALUES (?,?,?,?,?,?,?,?)",
                   (release_id, VERSION, VERSION, "published", json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    content_hash, "Codex", timestamp))
        position = 0
        for kind in ("industry", "field", "topic"):
            for item in taxonomy[kind]:
                position += 1
                db.execute("INSERT INTO v30_release_taxonomy VALUES (?,?,?,?,?)",
                           (release_id, kind, item[f"{kind}_id"], json.dumps(item, ensure_ascii=False, sort_keys=True), position))
        for position, (event, classification) in enumerate(records, 1):
            db.execute("INSERT INTO v30_release_records VALUES (?,?,?,?,?)",
                       (release_id, event["record_id"], json.dumps(event, ensure_ascii=False, sort_keys=True),
                        json.dumps(classification, ensure_ascii=False, sort_keys=True), position))
        db.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), "Codex", "create_v31_release", "v30_release", release_id, None,
                    json.dumps({"manifest": manifest, "content_hash": content_hash}, ensure_ascii=False),
                    "用户确认将21条来源复核及新增二、三级分类同步至网站；保留V3.0历史Release", None, timestamp))
    print(json.dumps({"release_id": release_id, "manifest": manifest, "content_hash": content_hash}, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
