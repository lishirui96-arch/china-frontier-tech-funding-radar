CREATE TABLE v14_event_units (
  event_unit_id TEXT PRIMARY KEY,
  audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  company_id TEXT NOT NULL REFERENCES v13_company_entities(company_id),
  canonical_event_id TEXT NOT NULL,
  event_sequence INTEGER NOT NULL DEFAULT 1,
  adjudicated_company_name TEXT NOT NULL,
  adjudicated_round TEXT NOT NULL,
  disclosure_date TEXT NOT NULL,
  amount_original TEXT NOT NULL,
  investors_original TEXT NOT NULL,
  sample_eligibility_status TEXT NOT NULL CHECK(sample_eligibility_status IN ('A_statistical','B_pending','C_excluded')),
  eligibility_reason TEXT NOT NULL,
  event_structure_status TEXT NOT NULL CHECK(event_structure_status IN ('single','split_recommended','duplicate_source','conflict_pending')),
  decision_status TEXT NOT NULL CHECK(decision_status IN ('automated_preparation','human_confirmed','human_modified')),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(audit_id,event_sequence,is_current)
);

CREATE TABLE v14_round_adjudications (
  adjudication_id TEXT PRIMARY KEY,
  audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  adjudication_type TEXT NOT NULL CHECK(adjudication_type IN ('A_historical_and_current','B_same_round_multiple_reports','C_distinct_rounds','D_staged_closing','E_media_conflict','F_unresolved')),
  original_round TEXT NOT NULL,
  proposed_rounds_json TEXT NOT NULL,
  basis TEXT NOT NULL,
  handling_recommendation TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('prepared','pending_human_review','confirmed')),
  created_at TEXT NOT NULL
);

CREATE TABLE v14_duplicate_decisions (
  decision_id TEXT PRIMARY KEY,
  relation_id TEXT NOT NULL REFERENCES v13_candidate_relations(relation_id),
  primary_event_id TEXT NOT NULL,
  secondary_event_id TEXT NOT NULL,
  final_decision TEXT NOT NULL CHECK(final_decision IN ('merge_sources','keep_distinct','pending_human_review')),
  basis TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('prepared','confirmed','pending_human_review')),
  created_at TEXT NOT NULL
);

CREATE TABLE v14_company_revisions (
  revision_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES v13_company_entities(company_id),
  audit_id TEXT NOT NULL REFERENCES v13_candidate_quality_audits(audit_id),
  original_name TEXT NOT NULL,
  confirmed_display_name TEXT NOT NULL,
  legal_name TEXT,
  english_name TEXT,
  revision_status TEXT NOT NULL CHECK(revision_status IN ('confirmed_display_name','pending_legal_entity','pending_name_review')),
  basis TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE v14_review_actions (
  action_id TEXT PRIMARY KEY,
  event_unit_id TEXT NOT NULL REFERENCES v14_event_units(event_unit_id),
  action_type TEXT NOT NULL CHECK(action_type IN ('confirm_company','rename_company','confirm_round','split_event','merge_duplicate','mark_statistical','hold','exclude')),
  actor TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
