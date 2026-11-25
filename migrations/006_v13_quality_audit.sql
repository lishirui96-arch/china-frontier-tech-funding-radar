CREATE TABLE v13_company_entities (
  company_id TEXT PRIMARY KEY,
  official_name TEXT,
  short_name TEXT NOT NULL,
  english_name TEXT,
  unified_social_credit_code TEXT,
  registered_location TEXT,
  official_website TEXT,
  primary_business TEXT NOT NULL,
  core_products TEXT NOT NULL,
  primary_category TEXT NOT NULL,
  secondary_track TEXT NOT NULL,
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending','conflict')),
  evidence_urls_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX idx_v13_company_short_name ON v13_company_entities(short_name);

CREATE TABLE v13_candidate_quality_audits (
  audit_id TEXT PRIMARY KEY,
  candidate_version TEXT NOT NULL CHECK(candidate_version IN ('V1.1','V1.2')),
  source_candidate_id TEXT NOT NULL,
  company_id TEXT NOT NULL REFERENCES v13_company_entities(company_id),
  original_company_name TEXT NOT NULL,
  normalized_company_name TEXT NOT NULL,
  original_disclosure_date TEXT NOT NULL,
  normalized_disclosure_date TEXT NOT NULL,
  original_round TEXT NOT NULL,
  normalized_round TEXT NOT NULL,
  original_amount TEXT NOT NULL,
  normalized_amount TEXT NOT NULL,
  original_investors TEXT NOT NULL,
  normalized_investors TEXT NOT NULL,
  original_primary_category TEXT NOT NULL,
  normalized_primary_category TEXT NOT NULL,
  original_secondary_track TEXT NOT NULL,
  normalized_secondary_track TEXT NOT NULL,
  source_title TEXT NOT NULL,
  source_url TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  name_quality_status TEXT NOT NULL CHECK(name_quality_status IN ('accurate','corrected','suspected_error','pending')),
  quality_issues_json TEXT NOT NULL,
  overall_verification_status TEXT NOT NULL CHECK(overall_verification_status IN ('complete','partial','pending','conflict','excluded')),
  audited_at TEXT NOT NULL,
  audit_method TEXT NOT NULL,
  UNIQUE(candidate_version,source_candidate_id)
);

CREATE TABLE v13_field_verifications (
  verification_id TEXT PRIMARY KEY,
  audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  field_name TEXT NOT NULL CHECK(field_name IN ('event_verified','company_verified','round_verified','amount_verified','investor_verified','date_verified','source_verified')),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending','conflict','not_applicable')),
  source_urls_json TEXT NOT NULL,
  evidence_excerpt TEXT NOT NULL,
  verification_method TEXT NOT NULL,
  verified_by TEXT NOT NULL,
  verified_at TEXT NOT NULL,
  UNIQUE(audit_id,field_name)
);
CREATE INDEX idx_v13_field_status ON v13_field_verifications(field_name,verification_status);

CREATE TABLE v13_candidate_relations (
  relation_id TEXT PRIMARY KEY,
  left_audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  right_audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  relation_type TEXT NOT NULL CHECK(relation_type IN ('confirmed_duplicate','confirmed_distinct','uncertain','multi_round_same_disclosure','supplemental_closing')),
  confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
  basis TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('resolved','pending_human_review')),
  created_at TEXT NOT NULL,
  UNIQUE(left_audit_id,right_audit_id,relation_type),
  CHECK(left_audit_id<>right_audit_id)
);

CREATE TABLE v13_official_evidence (
  official_evidence_id TEXT PRIMARY KEY,
  audit_id TEXT REFERENCES v13_candidate_quality_audits(audit_id),
  acquisition_key TEXT,
  evidence_type TEXT NOT NULL CHECK(evidence_type IN ('company_website','company_announcement','investor_announcement','exchange_filing','listed_company_announcement','official_account','not_found')),
  publisher TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,
  access_status TEXT NOT NULL,
  supported_fields_json TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  notes TEXT NOT NULL,
  collected_at TEXT NOT NULL
);

CREATE TABLE v13_change_history (
  change_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  field_name TEXT NOT NULL,
  original_value TEXT,
  normalized_value TEXT,
  reason TEXT NOT NULL,
  source_url TEXT,
  changed_by TEXT NOT NULL,
  changed_at TEXT NOT NULL
);

CREATE TABLE v13_acquisition_verifications (
  verification_id TEXT PRIMARY KEY,
  acquisition_key TEXT NOT NULL UNIQUE,
  acquisition_origin TEXT NOT NULL,
  buyer_name TEXT NOT NULL,
  target_name TEXT NOT NULL,
  equity_ratio_original TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  first_announcement_date TEXT NOT NULL,
  board_status TEXT NOT NULL,
  shareholder_status TEXT NOT NULL,
  regulatory_status TEXT NOT NULL,
  closing_status TEXT NOT NULL,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending','conflict')),
  source_urls_json TEXT NOT NULL,
  unresolved_fields TEXT NOT NULL,
  verified_at TEXT NOT NULL
);
