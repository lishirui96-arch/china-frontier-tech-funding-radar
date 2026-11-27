CREATE TABLE v35_event_clusters (
  cluster_id TEXT PRIMARY KEY,
  canonical_record_id TEXT REFERENCES v30_historical_records(record_id),
  cluster_status TEXT NOT NULL CHECK(cluster_status IN ('candidate','confirmed','reversed')),
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE v35_event_cluster_members (
  cluster_id TEXT NOT NULL REFERENCES v35_event_clusters(cluster_id),
  record_id TEXT NOT NULL UNIQUE REFERENCES v30_historical_records(record_id),
  legacy_unique_event_id TEXT NOT NULL,
  member_role TEXT NOT NULL CHECK(member_role IN ('canonical','source')),
  mapping_reason TEXT NOT NULL,
  source_merge_id TEXT REFERENCES v34_candidate_source_merges(merge_id),
  mapped_by TEXT NOT NULL,
  mapped_at TEXT NOT NULL,
  PRIMARY KEY(cluster_id,record_id)
);

CREATE INDEX idx_v35_cluster_members_cluster ON v35_event_cluster_members(cluster_id,member_role);
CREATE INDEX idx_v35_cluster_members_legacy ON v35_event_cluster_members(legacy_unique_event_id);

CREATE TABLE v35_collection_batches (
  batch_id TEXT PRIMARY KEY,
  batch_name TEXT NOT NULL UNIQUE,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  scope_note TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('planned','running','paused','completed','failed','reviewed')),
  source_count INTEGER NOT NULL DEFAULT 0,
  raw_source_count INTEGER NOT NULL DEFAULT 0,
  new_candidate_count INTEGER NOT NULL DEFAULT 0,
  duplicate_source_count INTEGER NOT NULL DEFAULT 0,
  effective_event_count INTEGER NOT NULL DEFAULT 0,
  vc_event_count INTEGER NOT NULL DEFAULT 0,
  early_event_count INTEGER NOT NULL DEFAULT 0,
  pending_round_count INTEGER NOT NULL DEFAULT 0,
  pending_classification_count INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  completed_at TEXT,
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE v35_collection_searches (
  search_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES v35_collection_batches(batch_id),
  search_date TEXT NOT NULL,
  source_name TEXT NOT NULL,
  query_text TEXT NOT NULL,
  result_count INTEGER NOT NULL DEFAULT 0,
  valid_result_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL CHECK(status IN ('planned','completed','no_result','failed')),
  notes TEXT NOT NULL DEFAULT '',
  searched_at TEXT NOT NULL
);

CREATE INDEX idx_v35_searches_batch ON v35_collection_searches(batch_id,search_date,source_name);

CREATE TABLE v35_historical_candidates (
  candidate_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES v35_collection_batches(batch_id),
  stable_event_id TEXT NOT NULL,
  company_name TEXT NOT NULL,
  announcement_date TEXT NOT NULL,
  transaction_date TEXT,
  round_original TEXT NOT NULL,
  round_bucket TEXT NOT NULL CHECK(round_bucket IN ('vc','early','pending','excluded')),
  amount_original TEXT NOT NULL,
  amount_currency TEXT,
  investors_original TEXT NOT NULL,
  primary_business TEXT NOT NULL,
  core_technology TEXT NOT NULL,
  evidence_grade TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','needs_verification','excluded','approved','rejected')),
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(batch_id,stable_event_id)
);

CREATE TABLE v35_candidate_sources (
  candidate_source_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  source_name TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  published_date TEXT,
  evidence_excerpt TEXT NOT NULL,
  is_primary INTEGER NOT NULL CHECK(is_primary IN (0,1)),
  access_status TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  UNIQUE(candidate_id,source_url)
);

CREATE TABLE v35_classification_proposals (
  proposal_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  proposal_type TEXT NOT NULL CHECK(proposal_type IN ('existing_taxonomy','new_field_or_topic','new_industry','pending_judgment')),
  proposed_industry_name TEXT,
  proposed_field_name TEXT,
  proposed_topic_name TEXT,
  existing_industry_id TEXT,
  existing_field_id TEXT,
  existing_topic_id TEXT,
  technical_boundary TEXT NOT NULL,
  difference_from_existing TEXT NOT NULL,
  proposal_reason TEXT NOT NULL,
  supporting_event_count INTEGER NOT NULL DEFAULT 1,
  supporting_company_count INTEGER NOT NULL DEFAULT 1,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','approved','rejected')),
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_v35_candidates_batch ON v35_historical_candidates(batch_id,announcement_date);
CREATE INDEX idx_v35_sources_candidate ON v35_candidate_sources(candidate_id);
CREATE INDEX idx_v35_proposals_candidate ON v35_classification_proposals(candidate_id,review_status);
