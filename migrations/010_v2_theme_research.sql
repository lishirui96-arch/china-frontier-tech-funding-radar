CREATE TABLE v2_industry_directions (industry_id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,description TEXT NOT NULL,sort_order INTEGER NOT NULL);
CREATE TABLE v2_technology_fields (field_id TEXT PRIMARY KEY,industry_id TEXT NOT NULL REFERENCES v2_industry_directions(industry_id),name TEXT NOT NULL,description TEXT NOT NULL,UNIQUE(industry_id,name));
CREATE TABLE v2_company_profiles (
 profile_id TEXT PRIMARY KEY,entity_key TEXT NOT NULL UNIQUE,company_name TEXT NOT NULL,source_entity_type TEXT NOT NULL,source_entity_id TEXT NOT NULL,
 primary_business TEXT NOT NULL,core_products TEXT NOT NULL,core_technologies TEXT NOT NULL,application_scenarios TEXT NOT NULL,value_chain_position TEXT NOT NULL,
 industry_id TEXT NOT NULL REFERENCES v2_industry_directions(industry_id),field_id TEXT NOT NULL REFERENCES v2_technology_fields(field_id),keywords_json TEXT NOT NULL,
 evidence_urls_json TEXT NOT NULL,profile_status TEXT NOT NULL CHECK(profile_status IN ('evidence_supported','partially_supported','pending_supplement')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE v2_candidate_topics (
 topic_id TEXT PRIMARY KEY,candidate_name TEXT NOT NULL,industry_id TEXT NOT NULL REFERENCES v2_industry_directions(industry_id),field_id TEXT NOT NULL REFERENCES v2_technology_fields(field_id),
 topic_description TEXT NOT NULL,technical_boundary TEXT NOT NULL,formation_basis TEXT NOT NULL,human_questions TEXT NOT NULL,
 topic_kind TEXT NOT NULL CHECK(topic_kind IN ('multi_company','single_company_observation')),review_status TEXT NOT NULL DEFAULT 'pending',final_name TEXT,final_name_locked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE v2_company_topic_links (topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),profile_id TEXT NOT NULL REFERENCES v2_company_profiles(profile_id),link_reason TEXT NOT NULL,is_current INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,PRIMARY KEY(topic_id,profile_id));
CREATE TABLE v2_event_topic_links (topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),event_source_type TEXT NOT NULL CHECK(event_source_type IN ('formal','A_candidate','B_candidate')),event_ref TEXT NOT NULL,company_name TEXT NOT NULL,round_original TEXT NOT NULL,amount_original TEXT NOT NULL,disclosure_date TEXT NOT NULL,PRIMARY KEY(topic_id,event_source_type,event_ref));
CREATE TABLE v2_topic_actions (action_id TEXT PRIMARY KEY,topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),action_type TEXT NOT NULL,actor TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,reason TEXT NOT NULL,occurred_at TEXT NOT NULL);
