from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TARGET = ROOT / "migrations" / "022_v37_taxonomy_upgrade.sql"


def rows(name: str) -> list[dict[str, str]]:
    with (DOCS / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def quote(value: str | None) -> str:
    if not value:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def values(items: list[tuple[str | None, ...]]) -> str:
    return ",\n".join("  (" + ",".join(quote(value) for value in item) + ")" for item in items)


def main() -> None:
    fields = [row for row in rows("V37_NEW_SECONDARY_FIELD_PROPOSALS.csv") if row["suggested_status"] == "recommended"]
    topics = [row for row in rows("V37_NEW_TERTIARY_TOPIC_PROPOSALS.csv") if row["suggested_status"] == "recommended"]
    mappings = rows("V37_HISTORICAL_MAPPING_ADJUSTMENTS.csv")
    if (len(fields), len(topics), len(mappings)) != (3, 6, 55):
        raise RuntimeError("V3.7 approved input counts changed")

    field_values = values([
        (row["proposal_id"], row["parent_industry_id"], row["classification_name"], str(900 + index), row["proposal_id"])
        for index, row in enumerate(fields, 1)
    ])
    topic_values = values([
        (row["proposal_id"], row["parent_id"], row["classification_name"], row["technical_boundary"],
         "formal", "approved", "V3.7_upgrade", row["proposal_id"], "v37:" + row["proposal_id"])
        for row in topics
    ])
    mapping_values = values([
        (row["candidate_id"], row["target_industry_id"], row["target_field_id"], row["target_topic_id"],
         row["mapping_basis"], row["source_url"])
        for row in mappings
    ])
    sql = f"""-- Approved V3.7 taxonomy upgrade. V3.2 remains immutable and queryable.
CREATE TABLE v37_taxonomy_settings (
  setting_key TEXT PRIMARY KEY CHECK(setting_key='current_taxonomy'),
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,reason TEXT NOT NULL
);

CREATE TABLE v37_taxonomy_version_mappings (
  entity_type TEXT NOT NULL CHECK(entity_type IN ('industry','field','topic')),
  source_taxonomy_version TEXT NOT NULL,source_entity_id TEXT NOT NULL,
  target_taxonomy_version TEXT NOT NULL,target_entity_id TEXT NOT NULL,
  relationship TEXT NOT NULL CHECK(relationship='preserved'),created_at TEXT NOT NULL,
  PRIMARY KEY(entity_type,source_taxonomy_version,source_entity_id,target_taxonomy_version),
  FOREIGN KEY(source_taxonomy_version) REFERENCES v30_taxonomy_versions(taxonomy_version),
  FOREIGN KEY(target_taxonomy_version) REFERENCES v30_taxonomy_versions(taxonomy_version)
);

CREATE TABLE v37_candidate_classifications (
  candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  stable_event_id TEXT NOT NULL,original_industry_id TEXT,original_field_id TEXT,original_topic_id TEXT,
  suggested_industry_id TEXT NOT NULL,suggested_field_id TEXT,suggested_topic_id TEXT,
  company_evidence TEXT NOT NULL,source_url TEXT NOT NULL,mapping_basis TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending_approval','approved','rejected')),
  created_at TEXT NOT NULL,created_by TEXT NOT NULL,
  PRIMARY KEY(candidate_id,taxonomy_version),
  FOREIGN KEY(taxonomy_version,suggested_industry_id) REFERENCES v30_industries(taxonomy_version,industry_id),
  FOREIGN KEY(taxonomy_version,suggested_field_id) REFERENCES v30_fields(taxonomy_version,field_id),
  FOREIGN KEY(taxonomy_version,suggested_topic_id) REFERENCES v30_topics(taxonomy_version,topic_id)
);

CREATE TABLE v37_taxonomy_upgrade_actions (
  action_id TEXT PRIMARY KEY,action_type TEXT NOT NULL,taxonomy_version TEXT NOT NULL,
  entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,
  reason TEXT NOT NULL,occurred_at TEXT NOT NULL,actor TEXT NOT NULL
);

INSERT INTO v30_taxonomy_versions
SELECT 'V3.7','frozen',22,'763f8b066667f247f9f0bfdf1af0a1e41a82e3d7','Codex',datetime('now'),datetime('now'),
       'Approved V3.7 taxonomy: preserve 10 primary industries, add 3 secondary fields and 6 tertiary topics'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.2');

INSERT INTO v30_industries
SELECT 'V3.7',industry_id,code,name,sort_order,source_industry_id
FROM v30_industries WHERE taxonomy_version='V3.2';

INSERT INTO v30_fields
SELECT 'V3.7',field_id,industry_id,name,sort_order,source_field_id
FROM v30_fields WHERE taxonomy_version='V3.2';

INSERT INTO v30_topics
SELECT 'V3.7',topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
FROM v30_topics WHERE taxonomy_version='V3.2';

INSERT INTO v30_topic_aliases
SELECT 'V3.7',alias_topic_id,canonical_topic_id,relation_type,reason,review_status
FROM v30_topic_aliases WHERE taxonomy_version='V3.2';

WITH approved(field_id,industry_id,name,sort_order,source_field_id) AS (VALUES
{field_values}
)
INSERT INTO v30_fields(taxonomy_version,field_id,industry_id,name,sort_order,source_field_id)
SELECT 'V3.7',field_id,industry_id,name,sort_order,source_field_id FROM approved
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

WITH approved(topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key) AS (VALUES
{topic_values}
)
INSERT INTO v30_topics(taxonomy_version,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key)
SELECT 'V3.7',topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
FROM approved WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

INSERT INTO v37_taxonomy_version_mappings
SELECT 'industry','V3.2',industry_id,'V3.7',industry_id,'preserved',datetime('now')
FROM v30_industries WHERE taxonomy_version='V3.2';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'field','V3.2',field_id,'V3.7',field_id,'preserved',datetime('now')
FROM v30_fields WHERE taxonomy_version='V3.2';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'topic','V3.2',topic_id,'V3.7',topic_id,'preserved',datetime('now')
FROM v30_topics WHERE taxonomy_version='V3.2';

WITH approved(candidate_id,suggested_industry_id,suggested_field_id,suggested_topic_id,mapping_basis,source_url) AS (VALUES
{mapping_values}
)
INSERT INTO v37_candidate_classifications(
  candidate_id,taxonomy_version,stable_event_id,original_industry_id,original_field_id,original_topic_id,
  suggested_industry_id,suggested_field_id,suggested_topic_id,company_evidence,source_url,mapping_basis,
  review_status,created_at,created_by
)
SELECT c.candidate_id,'V3.7',c.stable_event_id,p.existing_industry_id,p.existing_field_id,p.existing_topic_id,
       a.suggested_industry_id,a.suggested_field_id,a.suggested_topic_id,
       '主营业务：' || c.primary_business || '；核心技术：' || c.core_technology,
       a.source_url,a.mapping_basis,'pending_approval',datetime('now'),'Codex'
FROM approved a JOIN v35_historical_candidates c ON c.candidate_id=a.candidate_id
LEFT JOIN v35_classification_proposals p ON p.candidate_id=c.candidate_id;

INSERT INTO v37_taxonomy_settings
SELECT 'current_taxonomy','V3.7',datetime('now'),'Codex','User-approved V3.7 classification upgrade'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

INSERT INTO v37_taxonomy_upgrade_actions
SELECT 'v37-upgrade-' || entity_type || '-' || entity_id,'taxonomy_preserved','V3.7',entity_type,entity_id,
       '{{"taxonomy_version":"V3.2"}}','{{"taxonomy_version":"V3.7"}}',
       'Preserved original ID and parent relationship',datetime('now'),'Codex'
FROM (
  SELECT 'industry' entity_type,industry_id entity_id FROM v30_industries WHERE taxonomy_version='V3.2'
  UNION ALL SELECT 'field',field_id FROM v30_fields WHERE taxonomy_version='V3.2'
  UNION ALL SELECT 'topic',topic_id FROM v30_topics WHERE taxonomy_version='V3.2'
);

INSERT INTO v37_taxonomy_upgrade_actions
SELECT 'v37-current-version','activate_version','V3.7','taxonomy_version','V3.7',
       '{{"current":"V3.2"}}','{{"current":"V3.7"}}','User-approved formal taxonomy upgrade',datetime('now'),'Codex'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');
"""
    TARGET.write_text(sql, encoding="utf-8")


if __name__ == "__main__":
    main()
