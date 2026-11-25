CREATE TABLE source_audit_runs (
  run_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_column TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  robots_status TEXT NOT NULL,
  access_method TEXT NOT NULL,
  notes TEXT NOT NULL
);

CREATE TABLE source_audit_pages (
  page_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES source_audit_runs(run_id),
  page_number INTEGER NOT NULL,
  page_url TEXT NOT NULL,
  http_status INTEGER,
  article_count INTEGER NOT NULL,
  newest_date TEXT,
  oldest_date TEXT,
  access_status TEXT NOT NULL CHECK(access_status IN ('accessible','restricted','failed')),
  fetched_at TEXT NOT NULL,
  UNIQUE(run_id,page_url)
);

CREATE TABLE source_document_audit (
  document_id TEXT PRIMARY KEY REFERENCES raw_documents(document_id),
  source_column TEXT NOT NULL,
  page_access_status TEXT NOT NULL,
  original_access_status TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  duplicate_report INTEGER NOT NULL DEFAULT 0 CHECK(duplicate_report IN (0,1)),
  corresponding_event_id TEXT REFERENCES funding_events(event_id),
  discovery_channel TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  collected_at TEXT NOT NULL
);

CREATE TABLE v11_funding_candidates (
  candidate_id TEXT PRIMARY KEY,
  company_name_original TEXT NOT NULL,
  disclosure_date TEXT NOT NULL,
  round_original TEXT NOT NULL,
  round_normalized TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  source_document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  candidate_status TEXT NOT NULL CHECK(candidate_status IN ('verified_new','duplicate_v1','pending_verification','excluded')),
  duplicate_event_id TEXT REFERENCES funding_events(event_id),
  formal_event_id TEXT REFERENCES funding_events(event_id),
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  inclusion_reason TEXT NOT NULL,
  unresolved_fields TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_v11_candidates_status ON v11_funding_candidates(candidate_status,round_normalized);

CREATE TABLE source_event_observations (
  observation_id TEXT PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_column TEXT NOT NULL,
  external_key TEXT NOT NULL,
  document_id TEXT REFERENCES raw_documents(document_id),
  candidate_id TEXT REFERENCES v11_funding_candidates(candidate_id),
  event_id TEXT REFERENCES funding_events(event_id),
  is_duplicate_report INTEGER NOT NULL CHECK(is_duplicate_report IN (0,1)),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','pending','rejected')),
  notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(source_name,source_column,external_key)
);
