"""Seed only source whitelist and rule versions; never invent real financing events."""
from __future__ import annotations

import json

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now, uid


SOURCES = [
    ("企业官网", "company_official", "official", "A", None),
    ("投资机构官网", "investor_official", "official", "A", None),
    ("政府/监管正式来源", "government_regulatory", "official", "S", None),
    ("政府产业平台", "government_industry", "government", "B", None),
    ("高校成果转化平台", "university_transfer", "university", "B", None),
    ("可信专业媒体", "professional_media", "media", "B", None),
    ("行业媒体", "industry_media", "media", "C", None),
    ("聚合线索", "aggregator", "aggregator", "D", None),
]


def main() -> None:
    migrate()
    connection = connect()
    timestamp = now()
    try:
        with connection:
            for name, source_type, family, grade, url in SOURCES:
                connection.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?,?,?,?,?,?)", (uid(), name, source_type, family, grade, url, "review_required", timestamp))
            amount_definition = {"near": [0.8, 1.0], "several_ten_million": [20_000_000, 90_000_000], "several_hundred_million": [200_000_000, 900_000_000], "hundred_million_scale": [100_000_000, 999_999_999], "midpoint_forbidden": True}
            connection.execute("INSERT OR IGNORE INTO amount_rule_versions VALUES (?,?,?,?,?)", ("amount-v1", "1.0.0", json.dumps(amount_definition, sort_keys=True), 1, timestamp))
            dedup_definition = {"different_company_auto_merge": False, "date_windows_days": [7, 30, 45], "high_threshold": 0.75, "manual_threshold": 0.5}
            connection.execute("INSERT OR IGNORE INTO rule_versions VALUES (?,?,?,?,?,?)", ("dedup-v1", "dedup", "1.0.0", json.dumps(dedup_definition, sort_keys=True), 1, timestamp))
    finally:
        connection.close()
    print("Seeded source whitelist and versioned rules. No financing events were invented.")


if __name__ == "__main__":
    main()

