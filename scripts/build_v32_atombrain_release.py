from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from funding_radar.db import database_path


VERSION = "V3.2"
SOURCE_VERSION = "V3.1"
COMPANY = "原力无限INFIFORCE"
INDUSTRY = "机器人与具身智能"
FIELD = "具身大脑"
TOPIC = "具身大脑与机器人基础模型"
NS = uuid.UUID("5f8a1784-890f-4adc-8d02-b883a437e62b")


def uid(kind: str, value: str) -> str:
    return str(uuid.uuid5(NS, f"{kind}:{value}"))


def main() -> None:
    db = sqlite3.connect(database_path())
    db.row_factory = sqlite3.Row
    timestamp = datetime.now(timezone.utc).isoformat()
    source_release = db.execute(
        "SELECT * FROM v30_releases WHERE release_name=? AND status='published'", (SOURCE_VERSION,)
    ).fetchone()
    if not source_release:
        raise RuntimeError("V3.1 release is required")
    existing_release = db.execute("SELECT release_id FROM v30_releases WHERE release_name=?", (VERSION,)).fetchone()
    if existing_release:
        print(json.dumps({"release_id": existing_release["release_id"], "existing": True}, ensure_ascii=False))
        return

    with db:
        db.execute(
            "INSERT INTO v30_taxonomy_versions VALUES (?,?,?,?,?,?,?,?)",
            (VERSION, "draft", 17, "a35c1d3ec5159a866228e1332591449c6eb133f0", "Codex", timestamp, None,
             "根据用户提供的企业业务证据，将原力无限INFIFORCE归入机器人与具身智能，并新增具身大脑二级领域"),
        )
        db.execute(
            "INSERT INTO v30_industries SELECT ?,industry_id,code,name,sort_order,source_industry_id FROM v30_industries WHERE taxonomy_version=?",
            (VERSION, SOURCE_VERSION),
        )
        db.execute(
            "INSERT INTO v30_fields SELECT ?,field_id,industry_id,name,sort_order,source_field_id FROM v30_fields WHERE taxonomy_version=?",
            (VERSION, SOURCE_VERSION),
        )
        db.execute(
            """INSERT INTO v30_topics
               SELECT ?,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
               FROM v30_topics WHERE taxonomy_version=?""",
            (VERSION, SOURCE_VERSION),
        )
        db.execute(
            """INSERT INTO v30_topic_aliases
               SELECT ?,alias_topic_id,canonical_topic_id,relation_type,reason,review_status
               FROM v30_topic_aliases WHERE taxonomy_version=?""",
            (VERSION, SOURCE_VERSION),
        )
        industry = db.execute(
            "SELECT industry_id FROM v30_industries WHERE taxonomy_version=? AND name=?", (VERSION, INDUSTRY)
        ).fetchone()
        max_order = db.execute(
            "SELECT MAX(sort_order) FROM v30_fields WHERE taxonomy_version=? AND industry_id=?",
            (VERSION, industry["industry_id"]),
        ).fetchone()[0]
        field_id = uid("field", FIELD)
        topic_id = uid("topic", TOPIC)
        db.execute(
            "INSERT INTO v30_fields VALUES (?,?,?,?,?,?)",
            (VERSION, field_id, industry["industry_id"], FIELD, max_order + 1, "user-confirmed-v32-atombrain"),
        )
        db.execute(
            "INSERT INTO v30_topics VALUES (?,?,?,?,?,?,?,?,?,?)",
            (VERSION, topic_id, field_id, TOPIC,
             "面向机器人真实场景，以具身基础模型统一感知、认知、规划和行动，并推进工程化与规模化部署",
             "candidate", "user_classified", "user_evidence", "v32-atombrain", TOPIC.casefold()),
        )

        record = db.execute(
            "SELECT record_id FROM v30_historical_records WHERE company_name_standard=?", (COMPANY,)
        ).fetchone()
        db.execute(
            """UPDATE v31_pending_classification_reviews
               SET business_summary=?,product_summary=?,technology_summary=?,evidence_excerpt=?,
                   proposed_industry_name=?,proposed_field_name=?,proposed_topic_name=?,taxonomy_fit='new_field',
                   classification_confidence='high',classification_basis=?,needs_manual_review=0,review_status='user_confirmed'
               WHERE record_id=?""",
            ("具身大脑企业，为机器人真实场景提供感知、认知、规划与行动能力",
             "具身大脑AtomBrain",
             "具身基础模型、真实场景学习、机器人认知与决策控制",
             "用户补充：资金重点投向具身大脑AtomBrain技术研发、真实场景落地、工程化打磨与规模化产业化",
             INDUSTRY, FIELD, TOPIC,
             "企业核心产品为具身大脑AtomBrain，属于机器人与具身智能的认知决策基础模型层",
             record["record_id"]),
        )
        db.execute("UPDATE v30_record_classifications SET taxonomy_version=?,updated_at=?,updated_by=?",
                   (VERSION, timestamp, "codex_v32_sync"))
        db.execute(
            """UPDATE v30_record_classifications SET primary_industry_id=?,primary_field_id=?,primary_topic_id=?,
               classification_reason=?,confidence='high',needs_manual_review=0,classification_status='user_classified',
               updated_at=?,updated_by=? WHERE record_id=?""",
            (industry["industry_id"], field_id, topic_id,
             "用户确认企业为具身大脑企业，核心产品AtomBrain用于机器人真实场景的认知决策与行动",
             timestamp, "codex_v32_sync", record["record_id"]),
        )
        db.execute("DELETE FROM v30_record_topics WHERE record_id=?", (record["record_id"],))
        db.execute(
            "INSERT INTO v30_record_topics VALUES (?,?,?,?,?,?)",
            (record["record_id"], VERSION, topic_id, "primary", "用户确认的AtomBrain产品级依据", "user_confirmed"),
        )
        db.execute("UPDATE v30_taxonomy_versions SET status='frozen',frozen_at=? WHERE taxonomy_version=?", (timestamp, VERSION))

        taxonomy = {
            "industry": [dict(x) for x in db.execute("SELECT * FROM v30_industries WHERE taxonomy_version=? ORDER BY sort_order", (VERSION,))],
            "field": [dict(x) for x in db.execute("SELECT * FROM v30_fields WHERE taxonomy_version=? ORDER BY industry_id,sort_order", (VERSION,))],
            "topic": [dict(x) for x in db.execute("SELECT * FROM v30_topics WHERE taxonomy_version=? ORDER BY field_id,name", (VERSION,))],
        }
        records = []
        for row in db.execute(
            "SELECT record_id,event_snapshot_json,classification_snapshot_json FROM v30_release_records WHERE release_id=? ORDER BY position",
            (source_release["release_id"],),
        ):
            event = json.loads(row["event_snapshot_json"])
            classification = json.loads(row["classification_snapshot_json"])
            if row["record_id"] == record["record_id"]:
                event.update({
                    "amount_original": "数千万元",
                    "investors_original": json.dumps(["杭州资本"], ensure_ascii=False),
                    "primary_business": "具身大脑企业，为机器人真实场景提供感知、认知、规划与行动能力",
                    "core_products": "具身大脑AtomBrain",
                    "core_technologies": "具身基础模型、真实场景学习、机器人认知与决策控制",
                })
                classification.update({
                    "primary_industry_id": industry["industry_id"], "primary_field_id": field_id,
                    "primary_topic_id": topic_id, "topic_ids": [topic_id],
                    "topic_links": [{"topic_id": topic_id, "link_role": "primary", "basis": "用户确认的AtomBrain产品级依据", "review_status": "user_confirmed"}],
                    "confidence": "high", "needs_manual_review": 0, "classification_status": "user_classified",
                    "classification_reason": "用户确认企业为具身大脑企业，核心产品AtomBrain用于机器人真实场景的认知决策与行动",
                })
            records.append((event, classification))

        manifest = json.loads(source_release["manifest_json"])
        manifest.update({"taxonomy_version": VERSION, "fields": len(taxonomy["field"]), "topics": len(taxonomy["topic"]),
                         "classified": 97, "pending_classification": 0})
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
                   (str(uuid.uuid4()), "user", "classify_atombrain_and_create_v32_release", "v30_historical_record",
                    record["record_id"], json.dumps({"classification": "pending"}, ensure_ascii=False),
                    json.dumps({"industry": INDUSTRY, "field": FIELD, "topic": TOPIC, "amount": "数千万元", "investor": "杭州资本"}, ensure_ascii=False),
                    "用户提供企业主营产品和技术证据并明确要求归入具身大脑", None, timestamp))
    print(json.dumps({"release_id": release_id, "manifest": manifest, "content_hash": content_hash}, ensure_ascii=False))
    db.close()


if __name__ == "__main__":
    main()
