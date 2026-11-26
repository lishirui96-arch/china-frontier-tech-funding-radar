CREATE TABLE v34_candidate_source_merges (
  merge_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL,
  canonical_record_id TEXT NOT NULL REFERENCES v30_historical_records(record_id),
  duplicate_record_id TEXT NOT NULL UNIQUE REFERENCES v30_historical_records(record_id),
  canonical_round TEXT NOT NULL,
  decision_status TEXT NOT NULL CHECK(decision_status IN ('confirmed','reversed')),
  reason TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  CHECK(canonical_record_id <> duplicate_record_id)
);

CREATE INDEX idx_v34_source_merges_canonical ON v34_candidate_source_merges(canonical_record_id,decision_status);
