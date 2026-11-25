CREATE TABLE v211_profile_reviews (
 review_id TEXT PRIMARY KEY,profile_id TEXT NOT NULL UNIQUE REFERENCES v2_company_profiles(profile_id),quality_status TEXT NOT NULL,
 original_name TEXT NOT NULL,suggested_name TEXT NOT NULL,original_business TEXT NOT NULL,suggested_business TEXT NOT NULL,
 original_products TEXT NOT NULL,suggested_products TEXT NOT NULL,original_technologies TEXT NOT NULL,suggested_technologies TEXT NOT NULL,
 original_scenarios TEXT NOT NULL,suggested_scenarios TEXT NOT NULL,original_chain TEXT NOT NULL,suggested_chain TEXT NOT NULL,
 original_industry TEXT NOT NULL,suggested_industry TEXT NOT NULL,original_field TEXT NOT NULL,suggested_field TEXT NOT NULL,
 issues_json TEXT NOT NULL,reason TEXT NOT NULL,evidence_urls_json TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL);
CREATE TABLE v211_entity_duplicate_checks (
 check_id TEXT PRIMARY KEY,left_profile_id TEXT NOT NULL REFERENCES v2_company_profiles(profile_id),right_profile_id TEXT NOT NULL REFERENCES v2_company_profiles(profile_id),
 relation_suggestion TEXT NOT NULL,match_basis TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending',UNIQUE(left_profile_id,right_profile_id));
CREATE TABLE v211_product_technology_topic_links (
 link_id TEXT PRIMARY KEY,profile_id TEXT NOT NULL REFERENCES v2_company_profiles(profile_id),topic_id TEXT REFERENCES v2_candidate_topics(topic_id),
 product_basis TEXT NOT NULL,technology_basis TEXT NOT NULL,topic_fit TEXT NOT NULL,evidence_basis TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v211_shared_company_reviews (
 profile_id TEXT PRIMARY KEY REFERENCES v2_company_profiles(profile_id),topic_count INTEGER NOT NULL,review_conclusion TEXT NOT NULL,
 topic_basis_json TEXT NOT NULL,issues TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v211_split_proposals (
 proposal_id TEXT PRIMARY KEY,source_topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),subtopic_name TEXT NOT NULL,
 split_basis TEXT NOT NULL,company_count INTEGER NOT NULL,event_count INTEGER NOT NULL,formal_count INTEGER NOT NULL,a_count INTEGER NOT NULL,b_count INTEGER NOT NULL,
 qualifies_multi_company INTEGER NOT NULL,proposal_status TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v211_split_members (
 proposal_id TEXT NOT NULL REFERENCES v211_split_proposals(proposal_id),profile_id TEXT NOT NULL REFERENCES v2_company_profiles(profile_id),
 product_basis TEXT NOT NULL,technology_basis TEXT NOT NULL,PRIMARY KEY(proposal_id,profile_id));
CREATE TABLE v211_profile_actions (
 action_id TEXT PRIMARY KEY,review_id TEXT NOT NULL REFERENCES v211_profile_reviews(review_id),action_type TEXT NOT NULL,actor TEXT NOT NULL,
 before_json TEXT NOT NULL,after_json TEXT NOT NULL,reason TEXT NOT NULL,occurred_at TEXT NOT NULL);
