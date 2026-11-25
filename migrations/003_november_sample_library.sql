CREATE TABLE industry_categories (
  category_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  sort_order INTEGER NOT NULL UNIQUE,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1))
);

INSERT INTO industry_categories VALUES
  ('robotics','机器人与具身智能',1,1),
  ('ai_chips_manufacturing','AI芯片与先进制造',2,1),
  ('energy_materials','新能源与新材料',3,1),
  ('biomanufacturing','生物制造与合成生物学',4,1),
  ('quantum_computing','量子信息与先进计算',5,1),
  ('other_emerging','其他新兴技术方向',6,1);

CREATE TABLE sample_event_profiles (
  event_id TEXT PRIMARY KEY REFERENCES funding_events(event_id),
  sample_month TEXT NOT NULL,
  transaction_date TEXT,
  financing_type TEXT NOT NULL CHECK(financing_type IN ('early_financing','strategic_equity')),
  normalized_round TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES industry_categories(category_id),
  secondary_track TEXT NOT NULL,
  original_track TEXT,
  normalized_amount_cny INTEGER,
  valuation_original TEXT,
  coverage_cutoff TEXT NOT NULL,
  inclusion_status TEXT NOT NULL CHECK(inclusion_status IN ('included','held','excluded')),
  inclusion_reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(normalized_amount_cny IS NULL OR normalized_amount_cny >= 0)
);
CREATE INDEX idx_sample_profiles_month ON sample_event_profiles(sample_month,inclusion_status,normalized_round);
CREATE INDEX idx_sample_profiles_category ON sample_event_profiles(category_id,secondary_track);

CREATE TABLE acquisition_events (
  acquisition_id TEXT PRIMARY KEY,
  disclosure_date TEXT NOT NULL,
  transaction_date TEXT,
  sample_month TEXT NOT NULL,
  buyer_company_id TEXT REFERENCES companies(company_id),
  target_company_id TEXT REFERENCES companies(company_id),
  buyer_name_original TEXT NOT NULL,
  target_name_original TEXT NOT NULL,
  transaction_type TEXT NOT NULL CHECK(transaction_type IN ('acquisition','merger','control_acquisition','equity_acquisition','asset_acquisition','technology_acquisition')),
  transaction_status TEXT NOT NULL CHECK(transaction_status IN ('intent','announced','in_progress','completed','terminated','unknown')),
  amount_original TEXT NOT NULL,
  amount_currency TEXT NOT NULL CHECK(amount_currency IN ('CNY','USD','EUR','UNKNOWN')),
  amount_exact INTEGER,
  normalized_amount_cny INTEGER,
  category_id TEXT NOT NULL REFERENCES industry_categories(category_id),
  secondary_track TEXT NOT NULL,
  rationale_original TEXT,
  evidence_grade TEXT NOT NULL CHECK(evidence_grade IN ('S','A','B','C','D')),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending','rejected')),
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','approved','held','rejected')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(amount_exact IS NULL OR amount_exact >= 0),
  CHECK(normalized_amount_cny IS NULL OR normalized_amount_cny >= 0)
);
CREATE INDEX idx_acquisition_month ON acquisition_events(sample_month,transaction_status);

CREATE TABLE acquisition_documents (
  acquisition_id TEXT NOT NULL REFERENCES acquisition_events(acquisition_id),
  document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  relationship TEXT NOT NULL CHECK(relationship IN ('primary','supporting','duplicate_report','correction')),
  created_at TEXT NOT NULL,
  PRIMARY KEY(acquisition_id,document_id,relationship)
);

CREATE TABLE company_technology_profiles (
  profile_id TEXT PRIMARY KEY,
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  primary_business TEXT NOT NULL,
  core_products TEXT NOT NULL,
  core_technologies TEXT NOT NULL,
  application_scenarios TEXT NOT NULL,
  value_chain_position TEXT NOT NULL,
  technical_problem TEXT NOT NULL,
  funding_use TEXT,
  primary_category_id TEXT NOT NULL REFERENCES industry_categories(category_id),
  secondary_track TEXT NOT NULL,
  cross_domain_tags TEXT NOT NULL DEFAULT '[]',
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending')),
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','approved','held','rejected')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(company_id)
);

CREATE TABLE technology_profile_sources (
  profile_id TEXT NOT NULL REFERENCES company_technology_profiles(profile_id),
  document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  fields_json TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK(confidence IN ('verified','partially_verified','pending')),
  created_at TEXT NOT NULL,
  PRIMARY KEY(profile_id,document_id)
);

CREATE TABLE technology_keywords (
  keyword_id TEXT PRIMARY KEY,
  raw_keyword TEXT NOT NULL,
  normalized_keyword TEXT NOT NULL,
  description TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES industry_categories(category_id),
  verification_status TEXT NOT NULL CHECK(verification_status IN ('verified','partially_verified','pending')),
  created_at TEXT NOT NULL,
  UNIQUE(raw_keyword,normalized_keyword,category_id)
);
CREATE INDEX idx_keywords_normalized ON technology_keywords(normalized_keyword);

CREATE TABLE technology_keyword_links (
  keyword_id TEXT NOT NULL REFERENCES technology_keywords(keyword_id),
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  event_id TEXT REFERENCES funding_events(event_id),
  document_id TEXT NOT NULL REFERENCES raw_documents(document_id),
  relation TEXT NOT NULL CHECK(relation IN ('core','product','supporting','application')),
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','confirmed','rejected')),
  created_at TEXT NOT NULL,
  PRIMARY KEY(keyword_id,company_id,event_id,document_id)
);

CREATE TABLE candidate_themes (
  theme_id TEXT PRIMARY KEY,
  provisional_description TEXT NOT NULL,
  category_id TEXT NOT NULL REFERENCES industry_categories(category_id),
  value_chain_position TEXT NOT NULL,
  formation_basis TEXT NOT NULL,
  boundary_definition TEXT NOT NULL,
  review_questions TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending','keep','merge','split','hold','exclude')),
  final_name TEXT,
  final_name_locked INTEGER NOT NULL DEFAULT 0 CHECK(final_name_locked IN (0,1)),
  merged_into_theme_id TEXT REFERENCES candidate_themes(theme_id),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE candidate_theme_members (
  theme_id TEXT NOT NULL REFERENCES candidate_themes(theme_id),
  company_id TEXT NOT NULL REFERENCES companies(company_id),
  event_id TEXT NOT NULL REFERENCES funding_events(event_id),
  membership_reason TEXT NOT NULL,
  is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
  created_at TEXT NOT NULL,
  PRIMARY KEY(theme_id,company_id,event_id)
);

CREATE TABLE candidate_theme_keywords (
  theme_id TEXT NOT NULL REFERENCES candidate_themes(theme_id),
  keyword_id TEXT NOT NULL REFERENCES technology_keywords(keyword_id),
  PRIMARY KEY(theme_id,keyword_id)
);

CREATE TABLE candidate_theme_actions (
  action_id TEXT PRIMARY KEY,
  theme_id TEXT NOT NULL REFERENCES candidate_themes(theme_id),
  action_type TEXT NOT NULL CHECK(action_type IN ('rename','keep','merge','split','hold','exclude','move_company','restore')),
  actor TEXT NOT NULL,
  before_json TEXT NOT NULL,
  after_json TEXT NOT NULL,
  reason TEXT NOT NULL,
  occurred_at TEXT NOT NULL
);
CREATE INDEX idx_theme_actions ON candidate_theme_actions(theme_id,occurred_at);
