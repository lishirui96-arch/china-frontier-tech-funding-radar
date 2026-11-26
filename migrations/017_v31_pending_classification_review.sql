CREATE TABLE v31_pending_classification_reviews (
  review_id TEXT PRIMARY KEY,
  record_id TEXT NOT NULL UNIQUE REFERENCES v30_historical_records(record_id),
  company_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_title TEXT NOT NULL,
  business_summary TEXT NOT NULL,
  product_summary TEXT NOT NULL,
  technology_summary TEXT NOT NULL,
  evidence_excerpt TEXT NOT NULL,
  proposed_industry_name TEXT,
  proposed_field_name TEXT,
  proposed_topic_name TEXT,
  taxonomy_fit TEXT NOT NULL CHECK(taxonomy_fit IN ('existing','new_field','new_topic','pending')),
  classification_confidence TEXT NOT NULL CHECK(classification_confidence IN ('high','medium','low','unclassified')),
  classification_basis TEXT NOT NULL,
  needs_manual_review INTEGER NOT NULL CHECK(needs_manual_review IN (0,1)),
  review_status TEXT NOT NULL DEFAULT 'proposed',
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);

CREATE TABLE v31_taxonomy_extension_proposals (
  proposal_id TEXT PRIMARY KEY,
  parent_industry_name TEXT NOT NULL,
  proposed_field_name TEXT,
  parent_field_name TEXT,
  proposed_topic_name TEXT,
  supporting_companies_json TEXT NOT NULL,
  proposal_reason TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL
);
