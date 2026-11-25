CREATE TABLE v15_funding_review_queue (
  review_item_id TEXT PRIMARY KEY,
  event_unit_id TEXT NOT NULL UNIQUE REFERENCES v14_event_units(event_unit_id),
  queue_class TEXT NOT NULL CHECK(queue_class IN ('A','B')),
  batch_number INTEGER NOT NULL,
  issue_group TEXT NOT NULL,
  original_snapshot_json TEXT NOT NULL,
  suggested_company_name TEXT NOT NULL,
  suggested_round TEXT NOT NULL,
  suggested_primary_category TEXT NOT NULL,
  suggested_secondary_track TEXT NOT NULL,
  suggested_investors TEXT NOT NULL,
  suggested_notes TEXT NOT NULL DEFAULT '',
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','confirmed','held','excluded')),
  last_reviewed_at TEXT,
  last_reviewed_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE v15_confirmed_funding_events (
  confirmed_event_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL UNIQUE REFERENCES v15_funding_review_queue(review_item_id),
  company_id TEXT NOT NULL REFERENCES v13_company_entities(company_id),
  company_name TEXT NOT NULL,
  disclosure_date TEXT NOT NULL,
  round_original TEXT NOT NULL,
  round_confirmed TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  amount_currency TEXT,
  amount_cny REAL,
  investors TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  secondary_track TEXT NOT NULL,
  human_notes TEXT NOT NULL,
  confirmed_by TEXT NOT NULL,
  confirmed_at TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);

CREATE TABLE v15_funding_review_actions (
  action_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL REFERENCES v15_funding_review_queue(review_item_id),
  decision TEXT NOT NULL CHECK(decision IN ('confirm','hold','exclude','edit')),
  actor TEXT NOT NULL,
  original_snapshot_json TEXT NOT NULL,
  revised_snapshot_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);

CREATE TABLE v15_acquisition_review_queue (
  review_item_id TEXT PRIMARY KEY,
  acquisition_key TEXT NOT NULL UNIQUE,
  original_snapshot_json TEXT NOT NULL,
  confirmed_transaction_status TEXT,
  review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','confirmed','held','excluded')),
  human_notes TEXT NOT NULL DEFAULT '',
  last_reviewed_at TEXT,
  last_reviewed_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE v15_acquisition_review_actions (
  action_id TEXT PRIMARY KEY,
  review_item_id TEXT NOT NULL REFERENCES v15_acquisition_review_queue(review_item_id),
  decision TEXT NOT NULL CHECK(decision IN ('confirm_status','hold','exclude','edit')),
  actor TEXT NOT NULL,
  original_snapshot_json TEXT NOT NULL,
  revised_snapshot_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);

CREATE TABLE v15_technology_analysis (
  analysis_id TEXT PRIMARY KEY,
  confirmed_event_id TEXT NOT NULL UNIQUE REFERENCES v15_confirmed_funding_events(confirmed_event_id),
  company_id TEXT NOT NULL REFERENCES v13_company_entities(company_id),
  company_name TEXT NOT NULL,
  primary_business TEXT NOT NULL,
  core_products TEXT NOT NULL,
  core_technologies TEXT NOT NULL,
  technology_keywords TEXT NOT NULL,
  value_chain_position TEXT NOT NULL,
  application_scenarios TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  secondary_track TEXT NOT NULL,
  technology_source_urls_json TEXT NOT NULL,
  candidate_group TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
