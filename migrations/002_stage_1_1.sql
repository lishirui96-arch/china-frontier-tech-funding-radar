ALTER TABLE sources ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1));
ALTER TABLE sources ADD COLUMN allowed_scope TEXT NOT NULL DEFAULT 'metadata_only';
ALTER TABLE sources ADD COLUMN min_interval_seconds INTEGER NOT NULL DEFAULT 3600 CHECK(min_interval_seconds >= 0);
ALTER TABLE sources ADD COLUMN last_fetch_at TEXT;
ALTER TABLE sources ADD COLUMN failure_count INTEGER NOT NULL DEFAULT 0 CHECK(failure_count >= 0);

ALTER TABLE raw_documents ADD COLUMN source_domain TEXT;
ALTER TABLE raw_documents ADD COLUMN fetch_status TEXT NOT NULL DEFAULT 'manual' CHECK(fetch_status IN ('manual','pending','success','duplicate','restricted','failed'));
ALTER TABLE raw_documents ADD COLUMN financing_category TEXT NOT NULL DEFAULT 'undetermined' CHECK(financing_category IN ('primary_equity','merger_acquisition','ipo','private_placement','bond','bank_credit','government_subsidy','research_grant','non_financing','undetermined'));
ALTER TABLE raw_documents ADD COLUMN event_link_status TEXT NOT NULL DEFAULT 'unlinked' CHECK(event_link_status IN ('unlinked','candidate','linked','not_applicable'));
ALTER TABLE raw_documents ADD COLUMN imported_at TEXT;

CREATE TABLE import_batches (
  import_batch_id TEXT PRIMARY KEY, import_type TEXT NOT NULL CHECK(import_type IN ('single_url','bulk_url','csv','manual')),
  actor TEXT NOT NULL, submitted_count INTEGER NOT NULL, inserted_count INTEGER NOT NULL,
  duplicate_count INTEGER NOT NULL, failed_count INTEGER NOT NULL, errors_json TEXT NOT NULL,
  created_at TEXT NOT NULL, completed_at TEXT NOT NULL
);

CREATE TABLE discovery_runs (
  discovery_run_id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(source_id),
  run_type TEXT NOT NULL CHECK(run_type IN ('rss','news_page','government_page','university_page','public_search','manual')),
  started_at TEXT NOT NULL, completed_at TEXT, request_count INTEGER NOT NULL DEFAULT 0,
  inserted_count INTEGER NOT NULL DEFAULT 0, duplicate_count INTEGER NOT NULL DEFAULT 0,
  failure_count INTEGER NOT NULL DEFAULT 0, parser_version TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('running','success','partial','failed','skipped')),
  failure_summary TEXT, next_allowed_at TEXT
);
CREATE INDEX idx_discovery_runs_source_time ON discovery_runs(source_id, started_at);

CREATE TABLE discovery_failures (
  failure_id TEXT PRIMARY KEY, discovery_run_id TEXT NOT NULL REFERENCES discovery_runs(discovery_run_id),
  url TEXT, error_type TEXT NOT NULL, error_message TEXT NOT NULL, retryable INTEGER NOT NULL CHECK(retryable IN (0,1)),
  retry_after TEXT, occurred_at TEXT NOT NULL
);

CREATE TABLE extraction_candidates (
  extraction_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  field_group TEXT NOT NULL CHECK(field_group IN ('company','funding','investor')),
  field_name TEXT NOT NULL, raw_value TEXT NOT NULL, normalized_value TEXT,
  span_start INTEGER NOT NULL CHECK(span_start >= 0), span_end INTEGER NOT NULL CHECK(span_end >= span_start),
  confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1), extractor_version TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','confirmed','corrected','rejected')),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_extraction_document ON extraction_candidates(document_id, review_status);

CREATE TABLE review_rounds (
  review_round_id TEXT PRIMARY KEY, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
  round_number INTEGER NOT NULL CHECK(round_number IN (1,2)), reviewer TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('confirmed','needs_correction','held','rejected')),
  findings_json TEXT NOT NULL, reason TEXT NOT NULL, reviewed_at TEXT NOT NULL,
  UNIQUE(entity_type, entity_id, round_number)
);
CREATE INDEX idx_review_rounds_entity ON review_rounds(entity_type, entity_id);

CREATE TABLE release_status_history (
  release_status_id TEXT PRIMARY KEY, release_id TEXT NOT NULL REFERENCES releases(release_id),
  old_status TEXT, new_status TEXT NOT NULL CHECK(new_status IN ('published','withdrawn','superseded')),
  actor TEXT NOT NULL, reason TEXT NOT NULL, changed_at TEXT NOT NULL,
  audit_id TEXT NOT NULL REFERENCES audit_logs(audit_id)
);
CREATE INDEX idx_release_status_history ON release_status_history(release_id, changed_at);
