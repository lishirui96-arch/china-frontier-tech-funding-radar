CREATE TABLE v21_topic_audits (
 audit_id TEXT PRIMARY KEY,topic_id TEXT NOT NULL UNIQUE REFERENCES v2_candidate_topics(topic_id),recommendation TEXT NOT NULL,
 suggested_name TEXT, suggested_industry TEXT, suggested_field TEXT, commonality_assessment TEXT NOT NULL,
 boundary_assessment TEXT NOT NULL, problems_json TEXT NOT NULL, recommendation_reason TEXT NOT NULL,
 member_review_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE v21_topic_overlaps (
 left_topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),right_topic_id TEXT NOT NULL REFERENCES v2_candidate_topics(topic_id),
 shared_company_count INTEGER NOT NULL,jaccard REAL NOT NULL,relationship_type TEXT NOT NULL,review_note TEXT NOT NULL,
 PRIMARY KEY(left_topic_id,right_topic_id));
CREATE TABLE v21_taxonomy_proposals (
 proposal_id TEXT PRIMARY KEY,level TEXT NOT NULL,current_parent TEXT,current_name TEXT NOT NULL,suggested_parent TEXT,
 suggested_name TEXT NOT NULL,proposal_type TEXT NOT NULL,rationale TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v21_profile_triage (
 profile_id TEXT PRIMARY KEY REFERENCES v2_company_profiles(profile_id),was_pending INTEGER NOT NULL,was_other INTEGER NOT NULL,
 suggested_disposition TEXT NOT NULL,suggested_industry TEXT,suggested_field TEXT,suggested_topic TEXT,
 evidence_assessment TEXT NOT NULL,missing_fields TEXT NOT NULL,rationale TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
