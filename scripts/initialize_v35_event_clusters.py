from __future__ import annotations

import json

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


def initialize() -> dict[str, int]:
    migrate()
    timestamp = now()
    with connect() as connection, connection:
        records = {row["record_id"]: dict(row) for row in connection.execute(
            "SELECT record_id,unique_event_id FROM v30_historical_records"
        )}
        merges = {row["duplicate_record_id"]: dict(row) for row in connection.execute(
            "SELECT * FROM v34_candidate_source_merges WHERE decision_status='confirmed'"
        )}
        canonical_by_duplicate = {duplicate: item["canonical_record_id"] for duplicate, item in merges.items()}

        for record_id, record in records.items():
            if record_id in canonical_by_duplicate:
                continue
            cluster_id = record["unique_event_id"]
            connection.execute(
                "INSERT OR IGNORE INTO v35_event_clusters VALUES (?,?,?,?,?,?)",
                (cluster_id, record_id, "candidate", "system_v35", timestamp, timestamp),
            )
            connection.execute(
                """INSERT OR IGNORE INTO v35_event_cluster_members
                   VALUES (?,?,?,?,?,?,?,?)""",
                (cluster_id, record_id, record["unique_event_id"], "canonical",
                 "Preserve the canonical record's existing stable event ID.", None,
                 "system_v35", timestamp),
            )

        for duplicate_id, merge in merges.items():
            canonical = records[merge["canonical_record_id"]]
            duplicate = records[duplicate_id]
            connection.execute(
                """INSERT OR IGNORE INTO v35_event_cluster_members
                   VALUES (?,?,?,?,?,?,?,?)""",
                (canonical["unique_event_id"], duplicate_id, duplicate["unique_event_id"], "source",
                 merge["reason"], merge["merge_id"], "user_v34_decision", merge["decided_at"]),
            )

        counts = {
            "clusters": connection.execute("SELECT COUNT(*) FROM v35_event_clusters").fetchone()[0],
            "members": connection.execute("SELECT COUNT(*) FROM v35_event_cluster_members").fetchone()[0],
            "merged_sources": connection.execute("SELECT COUNT(*) FROM v35_event_cluster_members WHERE member_role='source'").fetchone()[0],
        }
        exists = connection.execute(
            "SELECT 1 FROM audit_logs WHERE action='initialize_stable_event_clusters_v35'"
        ).fetchone()
        if not exists:
            connection.execute(
                "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (uid(), "system_v35", "initialize_stable_event_clusters_v35", "v35_event_clusters",
                 "all", None, json.dumps(counts, ensure_ascii=False),
                 "Map 97 immutable source records to 95 stable event clusters using only confirmed V3.4 source-merge decisions.",
                 None, timestamp),
            )
    return counts


if __name__ == "__main__":
    print(json.dumps(initialize(), ensure_ascii=False))
