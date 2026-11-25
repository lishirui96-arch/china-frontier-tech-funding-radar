CREATE TABLE v151_research_policy (
  policy_id TEXT PRIMARY KEY,
  policy_version TEXT NOT NULL UNIQUE,
  valid_from TEXT NOT NULL,
  disclosure_start TEXT NOT NULL,
  disclosure_end TEXT NOT NULL,
  allowed_sources_json TEXT NOT NULL,
  evidence_baseline TEXT NOT NULL,
  company_name_standard TEXT NOT NULL,
  acquisition_standard TEXT NOT NULL,
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE v151_source_scope_checks (
  scope_check_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL UNIQUE REFERENCES v15_funding_review_queue(review_item_id),
  candidate_version TEXT NOT NULL,
  actual_source_platform TEXT NOT NULL,
  primary_url TEXT NOT NULL,
  pedaily_source_present INTEGER NOT NULL CHECK(pedaily_source_present IN (0,1)),
  spacedaily_source_present INTEGER NOT NULL CHECK(spacedaily_source_present IN (0,1)),
  source_scope_status TEXT NOT NULL CHECK(source_scope_status IN ('in_scope_pedaily','in_scope_spacedaily','out_of_scope_pending')),
  disclosure_date TEXT NOT NULL,
  date_scope_status TEXT NOT NULL CHECK(date_scope_status IN ('in_scope','out_of_scope')),
  handling_note TEXT NOT NULL,
  checked_at TEXT NOT NULL
);

CREATE TABLE v151_batch1_recommendations (
  recommendation_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL UNIQUE REFERENCES v15_funding_review_queue(review_item_id),
  company_name TEXT NOT NULL,
  original_amount TEXT NOT NULL,
  recommended_amount TEXT NOT NULL,
  original_round TEXT NOT NULL,
  recommended_round_display TEXT NOT NULL,
  queue_disclosure_date TEXT NOT NULL,
  source_page_date TEXT NOT NULL,
  investor_roles TEXT NOT NULL,
  name_recommendation TEXT NOT NULL,
  source_scope_status TEXT NOT NULL,
  review_attention TEXT NOT NULL,
  created_at TEXT NOT NULL
);
