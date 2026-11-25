CREATE TABLE v23_review_cards (
 card_id TEXT PRIMARY KEY,source_topic_id TEXT NOT NULL UNIQUE REFERENCES v22_topics(topic_id),candidate_class TEXT NOT NULL,
 recommendation TEXT NOT NULL,recommendation_reason TEXT NOT NULL,common_technology TEXT NOT NULL,independent_value TEXT NOT NULL,
 duplicate_note TEXT NOT NULL,member_details_json TEXT NOT NULL,event_details_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE v23_merge_previews (
 preview_id TEXT PRIMARY KEY,left_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),right_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),
 proposed_name TEXT NOT NULL,left_snapshot_json TEXT NOT NULL,right_snapshot_json TEXT NOT NULL,merged_company_count INTEGER NOT NULL,
 merged_event_count INTEGER NOT NULL,difference_json TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE v23_formal_topics (
 formal_topic_id TEXT PRIMARY KEY,field_id TEXT NOT NULL REFERENCES v22_fields(field_id),formal_name TEXT NOT NULL,topic_class TEXT NOT NULL,
 technical_boundary TEXT NOT NULL,review_status TEXT NOT NULL,confirmed_by TEXT NOT NULL,confirmed_at TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE v23_formal_topic_sources (
 formal_topic_id TEXT NOT NULL REFERENCES v23_formal_topics(formal_topic_id),source_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),
 relationship TEXT NOT NULL,PRIMARY KEY(formal_topic_id,source_topic_id));
CREATE TABLE v23_adjudications (
 adjudication_id TEXT PRIMARY KEY,source_topic_id TEXT NOT NULL REFERENCES v22_topics(topic_id),result_topic_id TEXT,
 decision TEXT NOT NULL,actor TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,reason TEXT NOT NULL,occurred_at TEXT NOT NULL);
