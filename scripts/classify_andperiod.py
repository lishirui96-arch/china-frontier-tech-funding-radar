from __future__ import annotations

from funding_radar.db import connect
from funding_radar.migrations import migrate
from funding_radar.repository import now


COMPANY = "安柏芮ANDPERIOD"
INDUSTRY_ID = "d97f43a8-6431-53ab-8a0f-7b249293c6ec"
FIELD_ID = "edc8b06e-95f5-5d50-bc86-eaa6c90b8398"
TOPIC_ID = "16e44396-6f2a-5182-8b1e-f5ea08500c80"


def apply_classification() -> str:
    migrate()
    timestamp = now()
    with connect() as connection, connection:
        candidate = connection.execute(
            "SELECT candidate_id,stable_event_id FROM v35_historical_candidates WHERE company_name=?",
            (COMPANY,),
        ).fetchone()
        if not candidate:
            raise RuntimeError(f"candidate not found: {COMPANY}")
        connection.execute(
            """UPDATE v35_classification_proposals
               SET proposal_type='existing_taxonomy',proposed_industry_name=NULL,
                   proposed_field_name=NULL,proposed_topic_name=NULL,existing_industry_id=?,
                   existing_field_id=?,existing_topic_id=?,technical_boundary=?,
                   difference_from_existing=?,proposal_reason=?,review_status='pending'
               WHERE candidate_id=?""",
            (INDUSTRY_ID, FIELD_ID, TOPIC_ID,
             "天然或生物基纤维通过材料结构、表面处理或复合工艺实现吸收、透气、低摩擦等功能。",
             "使用现有高性能功能材料领域与其他功能材料观察项，不修改V3.2冻结分类树。",
             "本轮资金用于Sylvenova专利云杉纤维面层量产，核心差异来自生物基功能材料。",
             candidate["candidate_id"]),
        )
        connection.execute(
            """INSERT INTO v37_candidate_classifications
               (candidate_id,taxonomy_version,stable_event_id,original_industry_id,original_field_id,
                original_topic_id,suggested_industry_id,suggested_field_id,suggested_topic_id,
                company_evidence,source_url,mapping_basis,review_status,created_at,created_by)
               SELECT c.candidate_id,'V3.7',c.stable_event_id,NULL,NULL,NULL,?,?,?,
                      '高端经期护理品牌；自主研发Sylvenova专利云杉纤维面层，本轮资金用于专利材料量产。',
                      s.source_url,?,'pending_approval',?,'codex_candidate_classification'
               FROM v35_historical_candidates c
               LEFT JOIN v35_candidate_sources s ON s.candidate_id=c.candidate_id
               WHERE c.candidate_id=?
               ON CONFLICT(candidate_id,taxonomy_version) DO UPDATE SET
                 suggested_industry_id=excluded.suggested_industry_id,
                 suggested_field_id=excluded.suggested_field_id,
                 suggested_topic_id=excluded.suggested_topic_id,
                 company_evidence=excluded.company_evidence,source_url=excluded.source_url,
                 mapping_basis=excluded.mapping_basis,review_status=excluded.review_status,
                 created_at=excluded.created_at,created_by=excluded.created_by""",
            (INDUSTRY_ID, FIELD_ID, TOPIC_ID,
             "按核心材料技术归类至新能源与先进材料/高性能功能材料/其他功能材料观察项。",
             timestamp, candidate["candidate_id"]),
        )
    return candidate["candidate_id"]


if __name__ == "__main__":
    print(apply_classification())
