CREATE TABLE v35_collection_search_results (
  result_id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES v35_collection_batches(batch_id),
  source_name TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  published_date TEXT NOT NULL,
  screening_status TEXT NOT NULL CHECK(screening_status IN ('candidate','excluded','needs_verification')),
  screening_reason TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  UNIQUE(batch_id,source_url)
);

CREATE INDEX idx_v35_search_results_batch ON v35_collection_search_results(batch_id,published_date,screening_status);
