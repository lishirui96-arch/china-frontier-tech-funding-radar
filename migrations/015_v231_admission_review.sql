CREATE TABLE v231_topic_admission_reviews (
 review_id TEXT PRIMARY KEY,source_topic_id TEXT NOT NULL UNIQUE REFERENCES v22_topics(topic_id),admission_conclusion TEXT NOT NULL,
 conclusion_reason TEXT NOT NULL,common_technology_claim TEXT NOT NULL,commonality_assessment TEXT NOT NULL,difference_assessment TEXT NOT NULL,
 boundary_assessment TEXT NOT NULL,cross_topic_notes TEXT NOT NULL,unique_company_count INTEGER NOT NULL,unique_event_count INTEGER NOT NULL,
 formal_count INTEGER NOT NULL,a_count INTEGER NOT NULL,b_count INTEGER NOT NULL,duplicate_risk TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE v231_member_quality (
 source_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),company_id TEXT NOT NULL REFERENCES v22_companies(company_id),quality_grade TEXT NOT NULL,
 business_assessment TEXT NOT NULL,product_assessment TEXT NOT NULL,technology_assessment TEXT NOT NULL,evidence_assessment TEXT NOT NULL,
 promotional_risk TEXT NOT NULL,admission_effect TEXT NOT NULL,PRIMARY KEY(source_topic_id,company_id));
CREATE TABLE v231_entity_reviews (
 entity_review_id TEXT PRIMARY KEY,left_company_id TEXT NOT NULL REFERENCES v22_companies(company_id),right_company_id TEXT NOT NULL REFERENCES v22_companies(company_id),
 name_assessment TEXT NOT NULL,legal_identifier_status TEXT NOT NULL,business_comparison TEXT NOT NULL,product_comparison TEXT NOT NULL,
 financing_comparison TEXT NOT NULL,recommendation TEXT NOT NULL,historical_id_mapping_json TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v231_cross_topic_reviews (
 company_id TEXT NOT NULL REFERENCES v22_companies(company_id),source_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),
 relationship_assessment TEXT NOT NULL,product_basis TEXT NOT NULL,technology_basis TEXT NOT NULL,recommendation TEXT NOT NULL,
 PRIMARY KEY(company_id,source_topic_id));
