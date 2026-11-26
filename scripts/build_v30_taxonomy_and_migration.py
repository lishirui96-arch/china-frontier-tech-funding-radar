from __future__ import annotations

import json
import sqlite3
import subprocess
import uuid
from datetime import datetime, timezone

from funding_radar.db import database_path
from funding_radar.migrations import migrate


VERSION = "V3.0"
NS = uuid.UUID("52a94ca8-8d3b-43f5-8f0c-31cb7df25129")


def uid(value: str) -> str:
    return str(uuid.uuid5(NS, value))


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    migrate()
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    timestamp = now()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with connection:
        connection.execute("INSERT OR IGNORE INTO v30_taxonomy_versions VALUES (?,?,?,?,?,?,?,?)",
                           (VERSION, "draft", 16, commit, "Codex", timestamp, None,
                            "从V2.2/V2.3/V2.3.1真实数据冻结；34条来源主题全部保留"))
        for row in connection.execute("SELECT * FROM v22_industries ORDER BY sort_order"):
            connection.execute("INSERT OR IGNORE INTO v30_industries VALUES (?,?,?,?,?,?)",
                               (VERSION, row["industry_id"], row["code"], row["name"], row["sort_order"], row["industry_id"]))
        for row in connection.execute("SELECT * FROM v22_fields ORDER BY industry_id,sort_order"):
            connection.execute("INSERT OR IGNORE INTO v30_fields VALUES (?,?,?,?,?,?)",
                               (VERSION, row["field_id"], row["industry_id"], row["name"], row["sort_order"], row["field_id"]))
        for row in connection.execute("SELECT * FROM v22_topics ORDER BY topic_id"):
            connection.execute("INSERT OR IGNORE INTO v30_topics VALUES (?,?,?,?,?,?,?,?,?,?)",
                               (VERSION, row["topic_id"], row["field_id"], row["candidate_name"], row["technical_boundary"],
                                row["management_status"], row["review_status"], row["source_kind"], row["source_ref"], row["canonical_key"]))
        for row in connection.execute("SELECT * FROM v22_topic_relations WHERE relation_type='conceptual_duplicate'"):
            connection.execute("INSERT OR IGNORE INTO v30_topic_aliases VALUES (?,?,?,?,?,?)",
                               (VERSION, row["right_topic_id"], row["left_topic_id"], row["relation_type"], row["reason"], row["review_status"]))

        queue = list(connection.execute("""SELECT q.*,s.actual_source_platform,s.primary_url,s.source_scope_status,s.disclosure_date
          FROM v15_funding_review_queue q JOIN v151_source_scope_checks s USING(review_item_id)
          ORDER BY s.disclosure_date DESC,q.suggested_company_name"""))
        for row in queue:
            source = json.loads(row["original_snapshot_json"])
            company = connection.execute("SELECT company_id FROM v22_companies WHERE display_name=? ORDER BY company_id LIMIT 1",
                                         (row["suggested_company_name"],)).fetchone()
            event = connection.execute("SELECT event_id FROM v22_events WHERE event_ref=?", (row["event_unit_id"],)).fetchone()
            migration_result = "classified_from_v2" if event else "recovered_unclassified"
            record_id = row["review_item_id"]
            connection.execute("INSERT OR IGNORE INTO v30_historical_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                record_id, row["review_item_id"], row["event_unit_id"], source["canonical_event_id"],
                company["company_id"] if company else None, source.get("original_company_name") or row["suggested_company_name"],
                row["suggested_company_name"], row["disclosure_date"], source.get("adjudicated_round") or row["suggested_round"],
                source.get("amount_original") or "未披露", source.get("investors_original") or row["suggested_investors"],
                row["actual_source_platform"], row["primary_url"], source.get("evidence_grade") or "B",
                row["review_status"], row["queue_class"], row["source_scope_status"], row["original_snapshot_json"],
                migration_result, timestamp))

            topics = []
            if event:
                topics = [dict(item) for item in connection.execute("""SELECT t.topic_id,t.field_id,f.industry_id,t.candidate_name
                  FROM v22_event_topics et JOIN v22_topics t USING(topic_id) JOIN v22_fields f USING(field_id)
                  WHERE et.event_id=? ORDER BY t.topic_id""", (event["event_id"],))]
            preferred = None
            if company and topics:
                preferred = connection.execute("SELECT primary_topic_id FROM v22_company_profiles WHERE company_id=?", (company["company_id"],)).fetchone()[0]
            primary = next((item for item in topics if item["topic_id"] == preferred), topics[0] if topics else None)
            if primary:
                reason = "继承V2事件主题关系；主主题优先采用企业产品技术画像的主要主题"
                confidence = "high" if preferred == primary["topic_id"] else "medium"
                status = "classified_proposed"
                needs_review = 0 if confidence == "high" and len(topics) == 1 else 1
                ids = (primary["industry_id"], primary["field_id"], primary["topic_id"])
            else:
                reason = "V2未建立可追溯的产品级主题关系；保留待分类，不根据标题或融资信息推断"
                confidence, status, needs_review, ids = "unclassified", "pending_manual_classification", 1, (None, None, None)
            connection.execute("INSERT OR IGNORE INTO v30_record_classifications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (record_id, VERSION, *ids, reason, confidence, needs_review, status, timestamp, "Codex"))
            for topic in topics:
                role = "primary" if topic["topic_id"] == ids[2] else "secondary"
                connection.execute("INSERT OR IGNORE INTO v30_record_topics VALUES (?,?,?,?,?,?)",
                                   (record_id, VERSION, topic["topic_id"], role,
                                    "V2事件—主题关系及V2.1.1企业产品技术画像", "suggested"))

        counts = {
            "industries": connection.execute("SELECT COUNT(*) FROM v30_industries WHERE taxonomy_version=?", (VERSION,)).fetchone()[0],
            "fields": connection.execute("SELECT COUNT(*) FROM v30_fields WHERE taxonomy_version=?", (VERSION,)).fetchone()[0],
            "topics": connection.execute("SELECT COUNT(*) FROM v30_topics WHERE taxonomy_version=?", (VERSION,)).fetchone()[0],
            "records": connection.execute("SELECT COUNT(*) FROM v30_historical_records").fetchone()[0],
        }
        if counts != {"industries": 10, "fields": 38, "topics": 34, "records": 97}:
            raise RuntimeError(f"V3.0 freeze count mismatch: {counts}")
        connection.execute("UPDATE v30_taxonomy_versions SET status='frozen',frozen_at=? WHERE taxonomy_version=? AND status='draft'",
                           (timestamp, VERSION))
    summary = dict(connection.execute("""SELECT COUNT(*) records,COUNT(DISTINCT unique_event_id) unique_events,
      SUM(migration_result='classified_from_v2') recovered_v2,SUM(migration_result='recovered_unclassified') recovered_gap
      FROM v30_historical_records""").fetchone())
    summary.update({"taxonomy": counts})
    print(json.dumps(summary, ensure_ascii=False))
    connection.close()


if __name__ == "__main__":
    main()
