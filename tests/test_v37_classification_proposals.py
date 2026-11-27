from __future__ import annotations

from scripts.write_v37_classification_proposals import proposal_id


def test_proposal_ids_are_stable_and_level_scoped():
    assert proposal_id("field", "可控核聚变工程") == proposal_id("field", "可控核聚变工程")
    assert proposal_id("field", "可控核聚变工程") != proposal_id("topic", "可控核聚变工程")
