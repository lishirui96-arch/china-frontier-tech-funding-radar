from __future__ import annotations

from scripts.write_v37_upgrade_preview import read_csv


def test_recommended_upgrade_counts_are_stable():
    fields = read_csv("V37_NEW_SECONDARY_FIELD_PROPOSALS.csv")
    topics = read_csv("V37_NEW_TERTIARY_TOPIC_PROPOSALS.csv")
    assert sum(row["suggested_status"] == "recommended" for row in fields) == 3
    assert sum(row["suggested_status"] == "recommended" for row in topics) == 6
