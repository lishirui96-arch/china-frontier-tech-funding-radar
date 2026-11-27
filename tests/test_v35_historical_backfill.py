from __future__ import annotations

from funding_radar.db import connect


def test_v35_foundation_tables_exist(db):
    connection = connect(db, read_only=True)
    try:
        names = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v35_%'"
        )}
        assert names == {
            "v35_event_clusters", "v35_event_cluster_members", "v35_collection_batches",
            "v35_collection_searches", "v35_historical_candidates", "v35_candidate_sources",
            "v35_classification_proposals",
            "v35_collection_search_results",
        }
    finally:
        connection.close()


def test_v35_batch_and_candidate_constraints(db):
    connection = connect(db)
    try:
        with connection:
            connection.execute(
                """INSERT INTO v35_collection_batches
                   (batch_id,batch_name,period_start,period_end,scope_note,status,created_by,created_at,updated_at)
                   VALUES ('batch','trial','2026-10-27','2026-11-01','all technology','planned','test','now','now')"""
            )
            connection.execute(
                """INSERT INTO v35_historical_candidates
                   VALUES ('candidate','batch','event','测试企业','2026-10-27',NULL,'A轮','vc','未披露',NULL,
                           '未披露','主营业务','核心技术','B','pending','test','now','now')"""
            )
        assert connection.execute("SELECT status FROM v35_collection_batches").fetchone()[0] == "planned"
        assert connection.execute("SELECT review_status FROM v35_historical_candidates").fetchone()[0] == "pending"
    finally:
        connection.close()
