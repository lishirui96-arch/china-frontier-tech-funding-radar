from __future__ import annotations

import json

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


DECISIONS = (
    {
        "company_id": "99eca7de-4c3d-5f82-88f9-fe66594b434b",
        "canonical_record_id": "8d33b2aa-d409-541e-a1d0-404ffa6b92c5",
        "duplicate_record_id": "64c351b5-649b-5cb8-b68b-1be2d24fbaaa",
        "canonical_round": "Pre-A+轮、A轮",
        "reason": "用户确认谱星航天两条记录属于同一融资披露的重复来源，仅保留一个合并事件视图。",
    },
    {
        "company_id": "c1b623e3-0bb8-57a9-bd14-9204c00ee8ef",
        "canonical_record_id": "7b89fbbd-76e0-5dcd-823f-24bce36bfca2",
        "duplicate_record_id": "aa8955bd-6fb2-5e0e-9bd1-430182932328",
        "canonical_round": "B+轮",
        "reason": "用户确认蓝固新能源两条记录属于同一融资事件的重复来源，以投资界披露记录为主记录。",
    },
)


def main() -> None:
    migrate()
    timestamp = now()
    with connect() as connection, connection:
        for item in DECISIONS:
            existing = connection.execute(
                "SELECT merge_id FROM v34_candidate_source_merges WHERE duplicate_record_id=?",
                (item["duplicate_record_id"],),
            ).fetchone()
            merge_id = existing["merge_id"] if existing else uid()
            connection.execute(
                """INSERT INTO v34_candidate_source_merges
                   (merge_id,company_id,canonical_record_id,duplicate_record_id,canonical_round,decision_status,reason,decided_by,decided_at)
                   VALUES (?,?,?,?,?,'confirmed',?,'user',?)
                   ON CONFLICT(duplicate_record_id) DO UPDATE SET
                     canonical_record_id=excluded.canonical_record_id,
                     canonical_round=excluded.canonical_round,
                     decision_status='confirmed',reason=excluded.reason,decided_by='user',decided_at=excluded.decided_at""",
                (merge_id, item["company_id"], item["canonical_record_id"], item["duplicate_record_id"],
                 item["canonical_round"], item["reason"], timestamp),
            )
            if not existing:
                connection.execute(
                    "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (uid(), "user", "confirm_duplicate_source_merge", "v30_historical_record",
                     item["duplicate_record_id"], None, json.dumps(item, ensure_ascii=False), item["reason"], None, timestamp),
                )
    print(json.dumps({"confirmed_source_merges": len(DECISIONS), "effective_candidate_events": 95}, ensure_ascii=False))


if __name__ == "__main__":
    main()
