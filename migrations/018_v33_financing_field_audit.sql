CREATE TABLE v33_financing_field_audits (
  audit_id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL UNIQUE REFERENCES v30_historical_records(record_id),
  source_url TEXT NOT NULL,
  source_http_status TEXT NOT NULL,
  original_amount TEXT NOT NULL,
  reviewed_amount TEXT NOT NULL,
  amount_status TEXT NOT NULL CHECK(amount_status IN ('verified','explicit_undisclosed','cumulative_only','combined_rounds','pending')),
  amount_evidence TEXT NOT NULL,
  original_investors TEXT NOT NULL,
  reviewed_investors TEXT NOT NULL,
  investor_status TEXT NOT NULL CHECK(investor_status IN ('verified','partially_verified','explicit_undisclosed','pending')),
  investor_evidence TEXT NOT NULL,
  financial_advisor_evidence TEXT NOT NULL,
  issues_json TEXT NOT NULL,
  reviewed_at TEXT NOT NULL,
  reviewed_by TEXT NOT NULL
);
