CREATE TABLE v12_source_records (
  source_record_id TEXT PRIMARY KEY,
  source_platform TEXT NOT NULL,
  external_record_id TEXT NOT NULL,
  company_name_original TEXT NOT NULL,
  company_name_english TEXT,
  disclosure_date TEXT NOT NULL,
  round_original TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  investors_original TEXT NOT NULL,
  sector_original TEXT NOT NULL,
  secondary_sector_original TEXT,
  source_title TEXT NOT NULL,
  original_url TEXT NOT NULL,
  platform_record_url TEXT NOT NULL,
  market_label_original TEXT,
  market_judgment TEXT NOT NULL CHECK(market_judgment IN ('confirmed_china','probable_china','not_china','pending')),
  market_judgment_basis TEXT NOT NULL,
  original_access_status TEXT NOT NULL CHECK(original_access_status IN ('accessible','inaccessible','thin_content','not_requested')),
  raw_json TEXT NOT NULL,
  collected_at TEXT NOT NULL,
  UNIQUE(source_platform,external_record_id)
);

CREATE TABLE v12_funding_candidates (
  candidate_id TEXT PRIMARY KEY,
  company_name_original TEXT NOT NULL,
  legal_name_candidate TEXT,
  disclosure_date TEXT NOT NULL,
  round_original TEXT NOT NULL,
  round_normalized TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  investors_original TEXT NOT NULL,
  source_track TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  secondary_track TEXT NOT NULL,
  source_title TEXT NOT NULL,
  original_url TEXT NOT NULL,
  source_platform TEXT NOT NULL,
  source_record_id TEXT REFERENCES v12_source_records(source_record_id),
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending','rejected')),
  candidate_status TEXT NOT NULL CHECK(candidate_status IN ('new','duplicate_v1_v11','pending_scope','excluded_round','excluded_market')),
  duplicate_candidate_id TEXT,
  duplicate_event_id TEXT REFERENCES funding_events(event_id),
  unresolved_fields TEXT NOT NULL,
  verification_notes TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(source_platform,source_record_id)
);
CREATE INDEX idx_v12_candidates_platform ON v12_funding_candidates(source_platform,candidate_status,verification_status);
CREATE INDEX idx_v12_candidates_company_date ON v12_funding_candidates(company_name_original,disclosure_date,round_normalized);

CREATE TABLE v12_platform_audits (
  platform TEXT PRIMARY KEY,
  base_url TEXT NOT NULL,
  robots_status TEXT NOT NULL,
  public_event_list TEXT NOT NULL,
  public_date_filter TEXT NOT NULL,
  public_pagination TEXT NOT NULL,
  article_access TEXT NOT NULL,
  pages_checked INTEGER NOT NULL,
  clues_found INTEGER NOT NULL,
  target_candidates INTEGER NOT NULL,
  inaccessible_count INTEGER NOT NULL,
  fields_unavailable TEXT NOT NULL,
  audit_notes TEXT NOT NULL,
  audited_at TEXT NOT NULL
);

CREATE TABLE v12_candidate_source_links (
  link_id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES v12_funding_candidates(candidate_id),
  source_platform TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  relationship TEXT NOT NULL CHECK(relationship IN ('primary','supporting','duplicate_report','official','discovery_only')),
  access_status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(candidate_id,source_url)
);

CREATE TABLE v12_acquisition_candidates (
  acquisition_candidate_id TEXT PRIMARY KEY,
  buyer_name TEXT NOT NULL,
  target_name TEXT NOT NULL,
  disclosure_date TEXT NOT NULL,
  transaction_type TEXT NOT NULL,
  equity_ratio_original TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  transaction_status TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_platform TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  verification_status TEXT NOT NULL,
  unresolved_fields TEXT NOT NULL,
  created_at TEXT NOT NULL
);
