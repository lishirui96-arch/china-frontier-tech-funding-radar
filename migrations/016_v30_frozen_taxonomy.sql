CREATE TABLE v30_taxonomy_versions (
  taxonomy_version TEXT PRIMARY KEY,status TEXT NOT NULL CHECK(status IN ('draft','frozen','retired')),
  source_schema_version INTEGER NOT NULL,source_commit TEXT NOT NULL,created_by TEXT NOT NULL,created_at TEXT NOT NULL,
  frozen_at TEXT,notes TEXT NOT NULL
);
CREATE TABLE v30_industries (
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),industry_id TEXT NOT NULL,
  code TEXT NOT NULL,name TEXT NOT NULL,sort_order INTEGER NOT NULL,source_industry_id TEXT NOT NULL,
  PRIMARY KEY(taxonomy_version,industry_id)
);
CREATE TABLE v30_fields (
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),field_id TEXT NOT NULL,
  industry_id TEXT NOT NULL,name TEXT NOT NULL,sort_order INTEGER NOT NULL,source_field_id TEXT NOT NULL,
  PRIMARY KEY(taxonomy_version,field_id),
  FOREIGN KEY(taxonomy_version,industry_id) REFERENCES v30_industries(taxonomy_version,industry_id)
);
CREATE TABLE v30_topics (
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),topic_id TEXT NOT NULL,
  field_id TEXT NOT NULL,name TEXT NOT NULL,technical_boundary TEXT NOT NULL,management_status TEXT NOT NULL,
  review_status TEXT NOT NULL,source_kind TEXT NOT NULL,source_ref TEXT NOT NULL,canonical_key TEXT NOT NULL,
  PRIMARY KEY(taxonomy_version,topic_id),
  FOREIGN KEY(taxonomy_version,field_id) REFERENCES v30_fields(taxonomy_version,field_id)
);
CREATE TABLE v30_topic_aliases (
  taxonomy_version TEXT NOT NULL,alias_topic_id TEXT NOT NULL,canonical_topic_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,reason TEXT NOT NULL,review_status TEXT NOT NULL,
  PRIMARY KEY(taxonomy_version,alias_topic_id,canonical_topic_id),
  FOREIGN KEY(taxonomy_version,alias_topic_id) REFERENCES v30_topics(taxonomy_version,topic_id),
  FOREIGN KEY(taxonomy_version,canonical_topic_id) REFERENCES v30_topics(taxonomy_version,topic_id)
);
CREATE TABLE v30_historical_records (
  record_id TEXT PRIMARY KEY,review_item_id TEXT NOT NULL UNIQUE,event_unit_id TEXT NOT NULL UNIQUE,
  unique_event_id TEXT NOT NULL UNIQUE,company_id TEXT REFERENCES v22_companies(company_id),company_name_original TEXT NOT NULL,
  company_name_standard TEXT NOT NULL,disclosure_date TEXT NOT NULL,round_original TEXT NOT NULL,
  amount_original TEXT NOT NULL,investors_original TEXT NOT NULL,source_platform TEXT NOT NULL,source_url TEXT NOT NULL,
  evidence_grade TEXT NOT NULL,original_review_status TEXT NOT NULL,queue_class TEXT NOT NULL,
  source_scope_status TEXT NOT NULL,source_snapshot_json TEXT NOT NULL,migration_result TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE v30_record_classifications (
  record_id TEXT PRIMARY KEY REFERENCES v30_historical_records(record_id),taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  primary_industry_id TEXT,primary_field_id TEXT,primary_topic_id TEXT,
  classification_reason TEXT NOT NULL,confidence TEXT NOT NULL CHECK(confidence IN ('high','medium','low','unclassified')),
  needs_manual_review INTEGER NOT NULL CHECK(needs_manual_review IN (0,1)),classification_status TEXT NOT NULL,
  updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,
  FOREIGN KEY(taxonomy_version,primary_industry_id) REFERENCES v30_industries(taxonomy_version,industry_id),
  FOREIGN KEY(taxonomy_version,primary_field_id) REFERENCES v30_fields(taxonomy_version,field_id),
  FOREIGN KEY(taxonomy_version,primary_topic_id) REFERENCES v30_topics(taxonomy_version,topic_id)
);
CREATE TABLE v30_record_topics (
  record_id TEXT NOT NULL REFERENCES v30_historical_records(record_id),taxonomy_version TEXT NOT NULL,
  topic_id TEXT NOT NULL,link_role TEXT NOT NULL CHECK(link_role IN ('primary','secondary')),
  basis TEXT NOT NULL,review_status TEXT NOT NULL,
  PRIMARY KEY(record_id,topic_id),
  FOREIGN KEY(taxonomy_version,topic_id) REFERENCES v30_topics(taxonomy_version,topic_id)
);
CREATE UNIQUE INDEX v30_one_primary_topic ON v30_record_topics(record_id) WHERE link_role='primary';
CREATE TABLE v30_classification_actions (
  action_id TEXT PRIMARY KEY,record_id TEXT NOT NULL REFERENCES v30_historical_records(record_id),action_type TEXT NOT NULL,
  actor TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,reason TEXT NOT NULL,occurred_at TEXT NOT NULL
);
CREATE TABLE v30_taxonomy_change_requests (
  request_id TEXT PRIMARY KEY,taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  target_type TEXT NOT NULL,target_id TEXT NOT NULL,change_type TEXT NOT NULL,proposed_value_json TEXT NOT NULL,
  actor TEXT NOT NULL,reason TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL
);
CREATE TABLE v30_releases (
  release_id TEXT PRIMARY KEY,release_name TEXT NOT NULL UNIQUE,taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  status TEXT NOT NULL CHECK(status IN ('published','withdrawn')),manifest_json TEXT NOT NULL,content_hash TEXT NOT NULL,
  created_by TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE TABLE v30_release_records (
  release_id TEXT NOT NULL REFERENCES v30_releases(release_id),record_id TEXT NOT NULL,event_snapshot_json TEXT NOT NULL,
  classification_snapshot_json TEXT NOT NULL,position INTEGER NOT NULL,PRIMARY KEY(release_id,record_id)
);
CREATE TABLE v30_release_taxonomy (
  release_id TEXT NOT NULL REFERENCES v30_releases(release_id),entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,position INTEGER NOT NULL,PRIMARY KEY(release_id,entity_type,entity_id)
);

CREATE TRIGGER v30_frozen_industries_no_update BEFORE UPDATE ON v30_industries
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_frozen_industries_no_delete BEFORE DELETE ON v30_industries
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_frozen_fields_no_update BEFORE UPDATE ON v30_fields
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_frozen_fields_no_delete BEFORE DELETE ON v30_fields
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_frozen_topics_no_update BEFORE UPDATE ON v30_topics
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_frozen_topics_no_delete BEFORE DELETE ON v30_topics
WHEN (SELECT status FROM v30_taxonomy_versions WHERE taxonomy_version=OLD.taxonomy_version)='frozen'
BEGIN SELECT RAISE(ABORT,'frozen taxonomy is immutable'); END;
CREATE TRIGGER v30_release_no_update BEFORE UPDATE ON v30_releases BEGIN SELECT RAISE(ABORT,'V3 release is immutable'); END;
CREATE TRIGGER v30_release_no_delete BEFORE DELETE ON v30_releases BEGIN SELECT RAISE(ABORT,'V3 release is immutable'); END;
CREATE TRIGGER v30_release_records_no_update BEFORE UPDATE ON v30_release_records BEGIN SELECT RAISE(ABORT,'V3 release is immutable'); END;
CREATE TRIGGER v30_release_records_no_delete BEFORE DELETE ON v30_release_records BEGIN SELECT RAISE(ABORT,'V3 release is immutable'); END;
