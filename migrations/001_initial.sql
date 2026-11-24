CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL
);

CREATE TABLE sources (
  source_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL,
  source_family TEXT NOT NULL, evidence_default_grade TEXT NOT NULL CHECK(evidence_default_grade IN ('S','A','B','C','D')),
  base_url TEXT, terms_status TEXT NOT NULL DEFAULT 'unknown', created_at TEXT NOT NULL
);

CREATE TABLE raw_documents (
  document_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(source_id),
  original_url TEXT NOT NULL, canonical_url TEXT NOT NULL, title TEXT NOT NULL,
  published_at TEXT, fetched_at TEXT NOT NULL, text_or_summary TEXT, content_hash TEXT NOT NULL,
  source_family TEXT NOT NULL, discovered_via_document_id TEXT REFERENCES raw_documents(document_id),
  archive_status TEXT NOT NULL CHECK(archive_status IN ('metadata_only','summary_saved','text_saved','restricted')),
  parser_version TEXT NOT NULL, relevance_status TEXT NOT NULL CHECK(relevance_status IN ('pending','relevant','irrelevant','uncertain')),
  review_status TEXT NOT NULL CHECK(review_status IN ('discovered','parsed','entity_review','dedup_review','field_review','approved','published','needs_correction','held','rejected')),
  created_at TEXT NOT NULL, UNIQUE(source_id, original_url)
);
CREATE INDEX idx_documents_hash ON raw_documents(content_hash);
CREATE INDEX idx_documents_review ON raw_documents(review_status, relevance_status);
CREATE INDEX idx_documents_canonical ON raw_documents(canonical_url);

CREATE TABLE companies (
  company_id TEXT PRIMARY KEY, official_name TEXT NOT NULL, short_name TEXT, english_name TEXT,
  region TEXT, official_domain TEXT, entity_kind TEXT NOT NULL DEFAULT 'legal_entity' CHECK(entity_kind IN ('legal_entity','brand','group','subsidiary')),
  normalization_status TEXT NOT NULL CHECK(normalization_status IN ('candidate','needs_review','confirmed','rejected')),
  human_review_status TEXT NOT NULL CHECK(human_review_status IN ('pending','confirmed','rejected')),
  evidence_document_id TEXT REFERENCES raw_documents(document_id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_companies_name ON companies(official_name);

CREATE TABLE company_aliases (
  alias_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id), alias TEXT NOT NULL,
  alias_type TEXT NOT NULL CHECK(alias_type IN ('short','former','english','brand','media')),
  evidence_document_id TEXT REFERENCES raw_documents(document_id), confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','confirmed','rejected')),
  created_at TEXT NOT NULL, UNIQUE(company_id, alias)
);
CREATE INDEX idx_company_alias ON company_aliases(alias);

CREATE TABLE investors (
  investor_id TEXT PRIMARY KEY, official_name TEXT NOT NULL, short_name TEXT, english_name TEXT,
  region TEXT, official_domain TEXT, investor_type TEXT NOT NULL CHECK(investor_type IN ('vc','pe','corporate','government_fund','university_fund','family_office','fund_vehicle','other','unknown')),
  normalization_status TEXT NOT NULL CHECK(normalization_status IN ('candidate','needs_review','confirmed','rejected')),
  human_review_status TEXT NOT NULL CHECK(human_review_status IN ('pending','confirmed','rejected')),
  evidence_document_id TEXT REFERENCES raw_documents(document_id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX idx_investors_name ON investors(official_name);

CREATE TABLE investor_aliases (
  alias_id TEXT PRIMARY KEY, investor_id TEXT NOT NULL REFERENCES investors(investor_id), alias TEXT NOT NULL,
  alias_type TEXT NOT NULL CHECK(alias_type IN ('short','former','english','brand','fund_vehicle','media')),
  evidence_document_id TEXT REFERENCES raw_documents(document_id), confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','confirmed','rejected')),
  created_at TEXT NOT NULL, UNIQUE(investor_id, alias)
);
CREATE INDEX idx_investor_alias ON investor_aliases(alias);

CREATE TABLE rule_versions (
  rule_version_id TEXT PRIMARY KEY, rule_type TEXT NOT NULL, version TEXT NOT NULL,
  definition_json TEXT NOT NULL, is_active INTEGER NOT NULL CHECK(is_active IN (0,1)), created_at TEXT NOT NULL,
  UNIQUE(rule_type, version)
);

CREATE TABLE amount_rule_versions (
  amount_rule_version_id TEXT PRIMARY KEY, version TEXT NOT NULL UNIQUE, definition_json TEXT NOT NULL,
  is_active INTEGER NOT NULL CHECK(is_active IN (0,1)), created_at TEXT NOT NULL
);

CREATE TABLE funding_events (
  event_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(company_id),
  announcement_date TEXT, announcement_date_end TEXT, round_original TEXT, round_normalized TEXT,
  amount_original TEXT NOT NULL, amount_exact INTEGER, amount_min INTEGER, amount_max INTEGER,
  amount_currency TEXT NOT NULL CHECK(amount_currency IN ('CNY','USD','EUR','UNKNOWN')),
  amount_disclosure_type TEXT NOT NULL CHECK(amount_disclosure_type IN ('exact','bounded_range','lower_bound','upper_bound','order_of_magnitude','undisclosed','cumulative_only')),
  amount_estimation_rule_id TEXT REFERENCES amount_rule_versions(amount_rule_version_id),
  amount_confidence REAL NOT NULL CHECK(amount_confidence BETWEEN 0 AND 1),
  is_cumulative_amount INTEGER NOT NULL CHECK(is_cumulative_amount IN (0,1)),
  use_of_funds_original TEXT, event_status TEXT NOT NULL CHECK(event_status IN ('candidate','active','superseded','withdrawn')),
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  review_status TEXT NOT NULL CHECK(review_status IN ('discovered','parsed','entity_review','dedup_review','field_review','approved','published','needs_correction','held','rejected')),
  related_event_id TEXT REFERENCES funding_events(event_id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  CHECK((amount_disclosure_type='exact' AND amount_exact IS NOT NULL AND is_cumulative_amount=0) OR (amount_disclosure_type<>'exact' AND amount_exact IS NULL)),
  CHECK(is_cumulative_amount=0 OR (amount_exact IS NULL AND amount_disclosure_type='cumulative_only')),
  CHECK(amount_min IS NULL OR amount_max IS NULL OR amount_min <= amount_max)
);
CREATE INDEX idx_events_company_date ON funding_events(company_id, announcement_date);
CREATE INDEX idx_events_review ON funding_events(review_status, evidence_grade);
CREATE INDEX idx_events_amount_type ON funding_events(amount_disclosure_type);

CREATE TABLE event_documents (
  event_id TEXT NOT NULL REFERENCES funding_events(event_id), document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  relationship TEXT NOT NULL CHECK(relationship IN ('primary','supporting','duplicate_report','correction','discovered_via')),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)), created_at TEXT NOT NULL,
  PRIMARY KEY(event_id, document_id, relationship)
);

CREATE TABLE event_investors (
  event_investor_id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES funding_events(event_id),
  investor_id TEXT NOT NULL REFERENCES investors(investor_id), role TEXT NOT NULL CHECK(role IN ('lead','follow','existing_additional','exclusive','undisclosed')),
  role_original TEXT, evidence_id TEXT, created_at TEXT NOT NULL, UNIQUE(event_id, investor_id, role)
);

CREATE TABLE evidence_records (
  evidence_id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  entity_type TEXT NOT NULL CHECK(entity_type IN ('company','investor','funding_event','event_investor')),
  entity_id TEXT NOT NULL, field_name TEXT NOT NULL, excerpt TEXT NOT NULL, span_start INTEGER, span_end INTEGER,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('pending','verified','rejected')),
  verified_by TEXT, verified_at TEXT, created_at TEXT NOT NULL,
  CHECK(span_start IS NULL OR span_start >= 0), CHECK(span_end IS NULL OR span_end >= span_start)
);
CREATE INDEX idx_evidence_entity ON evidence_records(entity_type, entity_id, field_name);

CREATE TABLE dedup_candidates (
  candidate_id TEXT PRIMARY KEY, left_event_id TEXT NOT NULL REFERENCES funding_events(event_id),
  right_event_id TEXT NOT NULL REFERENCES funding_events(event_id), rule_version_id TEXT NOT NULL REFERENCES rule_versions(rule_version_id),
  company_score REAL NOT NULL, date_score REAL NOT NULL, round_score REAL NOT NULL, amount_score REAL NOT NULL,
  investor_score REAL NOT NULL, text_score REAL NOT NULL, citation_score REAL NOT NULL,
  strong_conflicts_json TEXT NOT NULL, feature_details_json TEXT NOT NULL, total_score REAL NOT NULL,
  risk_level TEXT NOT NULL CHECK(risk_level IN ('low','medium','high')),
  status TEXT NOT NULL CHECK(status IN ('pending','resolved','withdrawn')),
  created_at TEXT NOT NULL, UNIQUE(left_event_id, right_event_id, rule_version_id), CHECK(left_event_id <> right_event_id)
);
CREATE INDEX idx_dedup_pending ON dedup_candidates(status, risk_level);

CREATE TABLE dedup_decisions (
  decision_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES dedup_candidates(candidate_id),
  decision TEXT NOT NULL CHECK(decision IN ('merge','do_not_merge','supplemental_disclosure','pending')),
  reason TEXT NOT NULL, decided_by TEXT NOT NULL, decided_at TEXT NOT NULL,
  rule_version_id TEXT NOT NULL REFERENCES rule_versions(rule_version_id), is_current INTEGER NOT NULL CHECK(is_current IN (0,1)),
  reverses_decision_id TEXT REFERENCES dedup_decisions(decision_id)
);
CREATE UNIQUE INDEX idx_dedup_current ON dedup_decisions(candidate_id) WHERE is_current=1;

CREATE TABLE audit_logs (
  audit_id TEXT PRIMARY KEY, actor TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL, before_json TEXT, after_json TEXT, reason TEXT NOT NULL,
  rule_version_id TEXT REFERENCES rule_versions(rule_version_id), occurred_at TEXT NOT NULL
);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id, occurred_at);

CREATE TABLE releases (
  release_id TEXT PRIMARY KEY, release_name TEXT NOT NULL UNIQUE, created_by TEXT NOT NULL,
  created_at TEXT NOT NULL, manifest_json TEXT NOT NULL, event_count INTEGER NOT NULL CHECK(event_count >= 0),
  content_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('published','withdrawn'))
);

CREATE TABLE release_events (
  release_id TEXT NOT NULL REFERENCES releases(release_id), event_id TEXT NOT NULL REFERENCES funding_events(event_id),
  event_snapshot_json TEXT NOT NULL, evidence_snapshot_json TEXT NOT NULL, position INTEGER NOT NULL,
  PRIMARY KEY(release_id, event_id), UNIQUE(release_id, position)
);

CREATE TRIGGER releases_immutable_update BEFORE UPDATE ON releases BEGIN SELECT RAISE(ABORT,'releases are immutable'); END;
CREATE TRIGGER releases_immutable_delete BEFORE DELETE ON releases BEGIN SELECT RAISE(ABORT,'releases are immutable'); END;
CREATE TRIGGER release_events_immutable_update BEFORE UPDATE ON release_events BEGIN SELECT RAISE(ABORT,'release events are immutable'); END;
CREATE TRIGGER release_events_immutable_delete BEFORE DELETE ON release_events BEGIN SELECT RAISE(ABORT,'release events are immutable'); END;

