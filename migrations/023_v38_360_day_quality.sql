-- V3.8 completes the 360-day classification audit and records confirmed duplicate reports.
CREATE TABLE v38_historical_duplicate_reports (
  canonical_candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  duplicate_candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  decision_status TEXT NOT NULL CHECK(decision_status IN ('confirmed','rejected')),
  reason TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  decided_by TEXT NOT NULL,
  PRIMARY KEY(canonical_candidate_id,duplicate_candidate_id)
);

INSERT INTO v30_taxonomy_versions
SELECT 'V3.8','frozen',23,'360-day-quality-audit','Codex',datetime('now'),datetime('now'),
       '360-day audit: 11 primary industries, with new payment, medical-device, mobility, smart-hardware and energy-system branches'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

INSERT INTO v30_industries
SELECT 'V3.8',industry_id,code,name,sort_order,source_industry_id
FROM v30_industries WHERE taxonomy_version='V3.7';
INSERT INTO v30_fields
SELECT 'V3.8',field_id,industry_id,name,sort_order,source_field_id
FROM v30_fields WHERE taxonomy_version='V3.7';
INSERT INTO v30_topics
SELECT 'V3.8',topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
FROM v30_topics WHERE taxonomy_version='V3.7';
INSERT INTO v30_topic_aliases
SELECT 'V3.8',alias_topic_id,canonical_topic_id,relation_type,reason,review_status
FROM v30_topic_aliases WHERE taxonomy_version='V3.7';

INSERT INTO v30_industries(taxonomy_version,industry_id,code,name,sort_order,source_industry_id)
SELECT 'V3.8','ff7843c2-7043-5859-bc3a-7d95cc558acf','FINTECH','金融科技与数字支付',1100,'ff7843c2-7043-5859-bc3a-7d95cc558acf'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.8');

WITH approved(taxonomy_version,field_id,industry_id,name,sort_order,source_field_id) AS (VALUES
('V3.8','e43b48e5-91b1-54b6-adf6-468d8dce6c3d','ff7843c2-7043-5859-bc3a-7d95cc558acf','数字支付基础设施',1101,'e43b48e5-91b1-54b6-adf6-468d8dce6c3d'),
('V3.8','cf0b00cc-55d4-523c-bd27-c6f000d85694','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','创新医疗器械',1102,'cf0b00cc-55d4-523c-bd27-c6f000d85694'),
('V3.8','c2f68702-f794-52e6-afde-02ab7b1409a6','596a5389-b98a-5194-80d4-6aab5261f7bc','智能交通与未来出行',1103,'c2f68702-f794-52e6-afde-02ab7b1409a6'),
('V3.8','b2c1949c-3f70-5dc4-90da-fc240e0b2881','596a5389-b98a-5194-80d4-6aab5261f7bc','智能硬件与人机交互',1104,'b2c1949c-3f70-5dc4-90da-fc240e0b2881'),
('V3.8','de2136fe-5f05-5d7c-9735-389d34e45bb4','d97f43a8-6431-53ab-8a0f-7b249293c6ec','新型能源系统与电力电子',1105,'de2136fe-5f05-5d7c-9735-389d34e45bb4'))
INSERT INTO v30_fields(taxonomy_version,field_id,industry_id,name,sort_order,source_field_id)
SELECT * FROM approved WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.8');

WITH approved(taxonomy_version,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key) AS (VALUES
('V3.8','f89a0b4b-ca01-55a9-b6cd-0f8138853199','e43b48e5-91b1-54b6-adf6-468d8dce6c3d','企业跨境支付与资金网络','直接提供企业支付、收款、资金管理或清算基础设施','formal','approved','V3.8_audit','f89a0b4b-ca01-55a9-b6cd-0f8138853199','v38:enterprise-crossborder-payments'),
('V3.8','6804f04e-df46-59d6-a533-72a991bd9767','cf0b00cc-55d4-523c-bd27-c6f000d85694','心血管介入与循环支持器械','直接研发血管介入、心室辅助或循环支持医疗器械','formal','approved','V3.8_audit','6804f04e-df46-59d6-a533-72a991bd9767','v38:vascular-intervention'),
('V3.8','3d633275-fce3-5828-823b-3589d7d7d3ed','c2f68702-f794-52e6-afde-02ab7b1409a6','智能两轮与低速出行系统','直接研发智能两轮、低速载运及其主动安全系统','formal','approved','V3.8_audit','3d633275-fce3-5828-823b-3589d7d7d3ed','v38:smart-two-wheel'),
('V3.8','cdc6c925-45e8-5bed-82a3-91cb83916ea4','c2f68702-f794-52e6-afde-02ab7b1409a6','智能运力与出行服务平台','以车队数字化、智能调度或出行基础设施为核心产品','formal','approved','V3.8_audit','cdc6c925-45e8-5bed-82a3-91cb83916ea4','v38:mobility-platform'),
('V3.8','b4b4ef73-4e4e-5693-942d-11d6dad6acbe','b2c1949c-3f70-5dc4-90da-fc240e0b2881','声学、触觉与可穿戴交互硬件','直接研发声学、骨传导、触觉反馈或可穿戴交互硬件','formal','approved','V3.8_audit','b4b4ef73-4e4e-5693-942d-11d6dad6acbe','v38:acoustic-haptic'),
('V3.8','0f8ca374-be5b-5901-836c-178a4306956f','de2136fe-5f05-5d7c-9735-389d34e45bb4','电力变换与直流能源基础设施','直接研发电能变换、直流配电或新型能源系统核心设备','formal','approved','V3.8_audit','0f8ca374-be5b-5901-836c-178a4306956f','v38:power-conversion'))
INSERT INTO v30_topics(taxonomy_version,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key)
SELECT * FROM approved WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.8');

INSERT INTO v37_taxonomy_version_mappings
SELECT 'industry','V3.7',industry_id,'V3.8',industry_id,'preserved',datetime('now') FROM v30_industries WHERE taxonomy_version='V3.7';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'field','V3.7',field_id,'V3.8',field_id,'preserved',datetime('now') FROM v30_fields WHERE taxonomy_version='V3.7';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'topic','V3.7',topic_id,'V3.8',topic_id,'preserved',datetime('now') FROM v30_topics WHERE taxonomy_version='V3.7';

INSERT INTO v37_candidate_classifications(
  candidate_id,taxonomy_version,stable_event_id,original_industry_id,original_field_id,original_topic_id,
  suggested_industry_id,suggested_field_id,suggested_topic_id,company_evidence,source_url,mapping_basis,
  review_status,created_at,created_by)
SELECT candidate_id,'V3.8',stable_event_id,original_industry_id,original_field_id,original_topic_id,
       suggested_industry_id,suggested_field_id,suggested_topic_id,company_evidence,source_url,mapping_basis,
       review_status,datetime('now'),'codex_v38_360_audit'
FROM v37_candidate_classifications WHERE taxonomy_version='V3.7';

WITH audited(candidate_id,industry_id,field_id,topic_id,basis) AS (VALUES
('b68569fe-e5ab-509f-af8c-bcea080f43aa','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','cf0b00cc-55d4-523c-bd27-c6f000d85694','6804f04e-df46-59d6-a533-72a991bd9767','有源能量血管介入产品矩阵'),
('8973f726-9f2d-5ebf-859e-7dd59c518740','ff7843c2-7043-5859-bc3a-7d95cc558acf','e43b48e5-91b1-54b6-adf6-468d8dce6c3d','f89a0b4b-ca01-55a9-b6cd-0f8138853199','企业跨境收、管、付数字支付基础设施'),
('8bac0da8-6bc4-554c-9d45-09ffa55eb6fe','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','ae3ab5bf-b59e-5caf-8660-a9ea2037c6ff',NULL,'衰老量化评估与健康干预服务'),
('f9c37f3c-f8e2-5c63-8898-894754a5ee5a','bbafb4a9-0ee3-539a-b811-15fd47677373','865740f5-b21b-58d3-bc36-14b5850359aa',NULL,'商业星载合成孔径雷达载荷'),
('360523d2-6451-5dd5-a3c2-3f1a7a4d4c11','596a5389-b98a-5194-80d4-6aab5261f7bc','ab8e5e92-382f-51f1-b210-735e7c2d83cb','db7b40b2-5b6a-55ee-9002-2c280871de20','线控角模块与智能底盘执行系统'),
('099dc8ec-4999-5c8d-b647-a631e453c272','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','cf0b00cc-55d4-523c-bd27-c6f000d85694',NULL,'医疗器械资产整合、注册与商业化'),
('0b0e0a05-7438-5ab2-bee3-dfae5071e123','d97f43a8-6431-53ab-8a0f-7b249293c6ec','e9970960-9052-57ec-af94-dc10cd0c7de7','3a6de858-d0ef-5a96-8c18-8640e655d4bf','小型模块化反应堆及微型反应堆'),
('2a1c5f9e-d88a-51c7-995b-0a2d6e4464e6','596a5389-b98a-5194-80d4-6aab5261f7bc','b2c1949c-3f70-5dc4-90da-fc240e0b2881','b4b4ef73-4e4e-5693-942d-11d6dad6acbe','骨传导耳机与触觉反馈硬件'),
('55e69d29-6087-523e-8a5e-eeaae70b4d60','c0983de5-d08f-53b8-901c-d750f8e863c2','e8b25a34-17ed-592d-8e9c-a68ae97ad80c',NULL,'面向失能群体的便携式洗澡机器人'),
('2b29612d-eef8-5a04-8dd8-ed512c3f1ba9','31fc4a30-6fb7-5de4-a08f-ea66cf052e26','15da02f1-6a39-5978-a626-ce9d66c2c5b8',NULL,'线下零售选址与流量决策智能'),
('39c829be-89fa-54c1-8918-2e976fae7299','596a5389-b98a-5194-80d4-6aab5261f7bc','c2f68702-f794-52e6-afde-02ab7b1409a6','cdc6c925-45e8-5bed-82a3-91cb83916ea4','车队运营与智能出行服务平台'),
('34c8ac9f-0003-524b-b721-ea6f13fa305a','596a5389-b98a-5194-80d4-6aab5261f7bc','c2f68702-f794-52e6-afde-02ab7b1409a6','3d633275-fce3-5828-823b-3589d7d7d3ed','自平衡智能两轮出行产品'),
('913e4ee7-6e25-53cb-93ce-b319dea9bacb','596a5389-b98a-5194-80d4-6aab5261f7bc','cad04295-6a2f-5b45-9641-a82de5596698',NULL,'关节臂测量机软硬件全栈国产化'),
('3fe7f6ba-ad70-5859-bba1-654da2a2ac0e','d97f43a8-6431-53ab-8a0f-7b249293c6ec','de2136fe-5f05-5d7c-9735-389d34e45bb4','0f8ca374-be5b-5901-836c-178a4306956f','直流化、高压化和柔性化电力系统'),
('9d2e431a-cdb3-52c4-b8ab-ac35227afbf1','596a5389-b98a-5194-80d4-6aab5261f7bc','c2f68702-f794-52e6-afde-02ab7b1409a6','3d633275-fce3-5828-823b-3589d7d7d3ed','低速短出行智能系统与主动安全'),
('0ae36c62-406b-527b-bd00-b76e9b87738f','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','cf0b00cc-55d4-523c-bd27-c6f000d85694','6804f04e-df46-59d6-a533-72a991bd9767','经皮心室辅助装置与循环支持系统'),
('eda87bc6-d8b8-52a8-a70b-30975524127e','31fc4a30-6fb7-5de4-a08f-ea66cf052e26','3329bbff-e4d9-5545-b6c7-2bbfb5b4d3ad',NULL,'通用AI智能体及个人智能助理')
)
INSERT OR REPLACE INTO v37_candidate_classifications(
 candidate_id,taxonomy_version,stable_event_id,original_industry_id,original_field_id,original_topic_id,
 suggested_industry_id,suggested_field_id,suggested_topic_id,company_evidence,source_url,mapping_basis,
 review_status,created_at,created_by)
SELECT a.candidate_id,'V3.8',c.stable_event_id,p.existing_industry_id,p.existing_field_id,p.existing_topic_id,
       a.industry_id,a.field_id,a.topic_id,substr(c.primary_business,1,800),s.source_url,a.basis,
       'pending_approval',datetime('now'),'codex_v38_360_audit'
FROM audited a JOIN v35_historical_candidates c USING(candidate_id)
LEFT JOIN v35_classification_proposals p USING(candidate_id)
JOIN v35_candidate_sources s ON s.candidate_id=c.candidate_id
 AND s.candidate_source_id=(SELECT MIN(s2.candidate_source_id) FROM v35_candidate_sources s2 WHERE s2.candidate_id=c.candidate_id);

INSERT INTO v38_historical_duplicate_reports
SELECT '0b0e0a05-7438-5ab2-bee3-dfae5071e123','fe5f8532-170d-54a1-8575-284034325aec','confirmed',
       '2026-07-23报道明确称天使轮系列融资，金额、轮次及多数机构与2026-05-22披露重合，按同一融资系列合并展示并保留双来源',
       datetime('now'),'codex_v38_360_audit'
WHERE EXISTS (SELECT 1 FROM v35_historical_candidates WHERE candidate_id='0b0e0a05-7438-5ab2-bee3-dfae5071e123')
  AND EXISTS (SELECT 1 FROM v35_historical_candidates WHERE candidate_id='fe5f8532-170d-54a1-8575-284034325aec');

UPDATE v37_taxonomy_settings SET taxonomy_version='V3.8',updated_at=datetime('now'),updated_by='Codex',
 reason='Completed 360-day duplicate and primary-classification audit' WHERE setting_key='current_taxonomy';

