-- Approved V3.7 taxonomy upgrade. V3.2 remains immutable and queryable.
CREATE TABLE v37_taxonomy_settings (
  setting_key TEXT PRIMARY KEY CHECK(setting_key='current_taxonomy'),
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  updated_at TEXT NOT NULL,updated_by TEXT NOT NULL,reason TEXT NOT NULL
);

CREATE TABLE v37_taxonomy_version_mappings (
  entity_type TEXT NOT NULL CHECK(entity_type IN ('industry','field','topic')),
  source_taxonomy_version TEXT NOT NULL,source_entity_id TEXT NOT NULL,
  target_taxonomy_version TEXT NOT NULL,target_entity_id TEXT NOT NULL,
  relationship TEXT NOT NULL CHECK(relationship='preserved'),created_at TEXT NOT NULL,
  PRIMARY KEY(entity_type,source_taxonomy_version,source_entity_id,target_taxonomy_version),
  FOREIGN KEY(source_taxonomy_version) REFERENCES v30_taxonomy_versions(taxonomy_version),
  FOREIGN KEY(target_taxonomy_version) REFERENCES v30_taxonomy_versions(taxonomy_version)
);

CREATE TABLE v37_candidate_classifications (
  candidate_id TEXT NOT NULL REFERENCES v35_historical_candidates(candidate_id),
  taxonomy_version TEXT NOT NULL REFERENCES v30_taxonomy_versions(taxonomy_version),
  stable_event_id TEXT NOT NULL,original_industry_id TEXT,original_field_id TEXT,original_topic_id TEXT,
  suggested_industry_id TEXT NOT NULL,suggested_field_id TEXT,suggested_topic_id TEXT,
  company_evidence TEXT NOT NULL,source_url TEXT NOT NULL,mapping_basis TEXT NOT NULL,
  review_status TEXT NOT NULL CHECK(review_status IN ('pending_approval','approved','rejected')),
  created_at TEXT NOT NULL,created_by TEXT NOT NULL,
  PRIMARY KEY(candidate_id,taxonomy_version),
  FOREIGN KEY(taxonomy_version,suggested_industry_id) REFERENCES v30_industries(taxonomy_version,industry_id),
  FOREIGN KEY(taxonomy_version,suggested_field_id) REFERENCES v30_fields(taxonomy_version,field_id),
  FOREIGN KEY(taxonomy_version,suggested_topic_id) REFERENCES v30_topics(taxonomy_version,topic_id)
);

CREATE TABLE v37_taxonomy_upgrade_actions (
  action_id TEXT PRIMARY KEY,action_type TEXT NOT NULL,taxonomy_version TEXT NOT NULL,
  entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,
  reason TEXT NOT NULL,occurred_at TEXT NOT NULL,actor TEXT NOT NULL
);

INSERT INTO v30_taxonomy_versions
SELECT 'V3.7','frozen',22,'763f8b066667f247f9f0bfdf1af0a1e41a82e3d7','Codex',datetime('now'),datetime('now'),
       'Approved V3.7 taxonomy: preserve 10 primary industries, add 3 secondary fields and 6 tertiary topics'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.2');

INSERT INTO v30_industries
SELECT 'V3.7',industry_id,code,name,sort_order,source_industry_id
FROM v30_industries WHERE taxonomy_version='V3.2';

INSERT INTO v30_fields
SELECT 'V3.7',field_id,industry_id,name,sort_order,source_field_id
FROM v30_fields WHERE taxonomy_version='V3.2';

INSERT INTO v30_topics
SELECT 'V3.7',topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
FROM v30_topics WHERE taxonomy_version='V3.2';

INSERT INTO v30_topic_aliases
SELECT 'V3.7',alias_topic_id,canonical_topic_id,relation_type,reason,review_status
FROM v30_topic_aliases WHERE taxonomy_version='V3.2';

WITH approved(field_id,industry_id,name,sort_order,source_field_id) AS (VALUES
  ('715204f3-bd31-5370-9c1d-baf9c813364b','d97f43a8-6431-53ab-8a0f-7b249293c6ec','可控核聚变工程','901','715204f3-bd31-5370-9c1d-baf9c813364b'),
  ('e9970960-9052-57ec-af94-dc10cd0c7de7','d97f43a8-6431-53ab-8a0f-7b249293c6ec','先进裂变能与小型反应堆','902','e9970960-9052-57ec-af94-dc10cd0c7de7'),
  ('ab8e5e92-382f-51f1-b210-735e7c2d83cb','596a5389-b98a-5194-80d4-6aab5261f7bc','智能底盘与线控系统','903','ab8e5e92-382f-51f1-b210-735e7c2d83cb')
)
INSERT INTO v30_fields(taxonomy_version,field_id,industry_id,name,sort_order,source_field_id)
SELECT 'V3.7',field_id,industry_id,name,sort_order,source_field_id FROM approved
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

WITH approved(topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key) AS (VALUES
  ('30e3c50c-5258-5dc6-bfce-64f0468ec7bf','715204f3-bd31-5370-9c1d-baf9c813364b','磁约束聚变系统工程','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','30e3c50c-5258-5dc6-bfce-64f0468ec7bf','v37:30e3c50c-5258-5dc6-bfce-64f0468ec7bf'),
  ('a932adda-5b3b-552c-b63f-5309a496ec53','715204f3-bd31-5370-9c1d-baf9c813364b','惯性约束与激光聚变系统','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','a932adda-5b3b-552c-b63f-5309a496ec53','v37:a932adda-5b3b-552c-b63f-5309a496ec53'),
  ('3a6de858-d0ef-5a96-8c18-8640e655d4bf','e9970960-9052-57ec-af94-dc10cd0c7de7','小型模块化反应堆与微型核能系统','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','3a6de858-d0ef-5a96-8c18-8640e655d4bf','v37:3a6de858-d0ef-5a96-8c18-8640e655d4bf'),
  ('01057042-e097-58bf-b94d-0bc4532ba1f9','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','超导材料与强场磁体','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','01057042-e097-58bf-b94d-0bc4532ba1f9','v37:01057042-e097-58bf-b94d-0bc4532ba1f9'),
  ('db7b40b2-5b6a-55ee-9002-2c280871de20','ab8e5e92-382f-51f1-b210-735e7c2d83cb','线控制动与底盘执行系统','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','db7b40b2-5b6a-55ee-9002-2c280871de20','v37:db7b40b2-5b6a-55ee-9002-2c280871de20'),
  ('cd096937-b9a3-5abe-a0ee-7880fdbe62bb','31fc3cbf-4043-521a-b380-b6d3f3b14dca','AR智能眼镜与空间计算终端','只纳入直接开发该技术、部件或系统的企业，不以应用场景或投资方标签代替技术证据','formal','approved','V3.7_upgrade','cd096937-b9a3-5abe-a0ee-7880fdbe62bb','v37:cd096937-b9a3-5abe-a0ee-7880fdbe62bb')
)
INSERT INTO v30_topics(taxonomy_version,topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key)
SELECT 'V3.7',topic_id,field_id,name,technical_boundary,management_status,review_status,source_kind,source_ref,canonical_key
FROM approved WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

INSERT INTO v37_taxonomy_version_mappings
SELECT 'industry','V3.2',industry_id,'V3.7',industry_id,'preserved',datetime('now')
FROM v30_industries WHERE taxonomy_version='V3.2';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'field','V3.2',field_id,'V3.7',field_id,'preserved',datetime('now')
FROM v30_fields WHERE taxonomy_version='V3.2';
INSERT INTO v37_taxonomy_version_mappings
SELECT 'topic','V3.2',topic_id,'V3.7',topic_id,'preserved',datetime('now')
FROM v30_topics WHERE taxonomy_version='V3.2';

WITH approved(candidate_id,suggested_industry_id,suggested_field_id,suggested_topic_id,mapping_basis,source_url) AS (VALUES
  ('bcd08f75-9164-5b5c-b23c-3ebe564cd502','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','16e44396-6f2a-5182-8b1e-f5ea08500c80','来源标题出现直接技术信号：电化学合成；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558212.shtml'),
  ('2a20f04c-fe96-5313-a5bb-17f71493ef65','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558307.shtml'),
  ('da45c892-7107-5ce3-88a4-f07fc80b4b0d','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558308.shtml'),
  ('50f26388-bd90-5cb3-8eb9-9f9de6f06471','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','ae3ab5bf-b59e-5caf-8660-a9ea2037c6ff',NULL,'来源标题出现直接技术信号：健康管理；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558364.shtml'),
  ('2ac183d9-300f-5c87-863e-43d6119792b4','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'企业开头简介出现3次一致技术信号：生物、医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558467.shtml'),
  ('4bcfb48a-ce68-5218-b1f0-3cf48268bb8a','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'企业开头简介出现3次一致技术信号：生物、医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202512/558467.shtml'),
  ('a6941a14-3da4-5ebd-aeb2-abd41f41997f','5d20ce7f-cb8d-50fe-8b72-518666a7dce3',NULL,NULL,'来源标题出现直接技术信号：智驾；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/559609.shtml'),
  ('cb19a936-e3c8-5bef-beab-4c36202af5eb','5d20ce7f-cb8d-50fe-8b72-518666a7dce3',NULL,NULL,'企业开头简介出现2次一致技术信号：自动驾驶、智驾；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/559905.shtml'),
  ('9bb565b5-3b6e-5871-ba09-0f04db8177e3','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/560017.shtml'),
  ('890c98af-da5a-5e36-b623-c4a6c146eab0','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','16e44396-6f2a-5182-8b1e-f5ea08500c80','来源标题出现直接技术信号：新材；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/560169.shtml'),
  ('87d9619f-4284-5a44-a675-a5f6982abf39','c9a16792-5f10-51fb-9437-875c75b8a7f0','23065258-afd9-5a5b-8cf8-9b763c8a5e01',NULL,'来源标题出现直接技术信号：微纳；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/560276.shtml'),
  ('185bdfe7-b6ec-5c46-9a2c-7dbb1a488a5e','c9a16792-5f10-51fb-9437-875c75b8a7f0',NULL,NULL,'来源标题出现直接技术信号：光电；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/560403.shtml'),
  ('c9f0e9d8-2d9e-5963-8e71-f7b63511111c','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202601/560573.shtml'),
  ('1b162b83-9935-5842-92ce-ad185f0b7263','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202602/560667.shtml'),
  ('2ad3b302-90da-5b15-9930-b5fa724d56f7','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202603/561672.shtml'),
  ('4c4975b9-a6bd-596d-a3f0-b6e01b7cda1d','596a5389-b98a-5194-80d4-6aab5261f7bc','cad04295-6a2f-5b45-9641-a82de5596698',NULL,'来源标题出现直接技术信号：精仪；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202603/562092.shtml'),
  ('880f16db-1fe0-51d2-a657-772636a58ed1','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','ae3ab5bf-b59e-5caf-8660-a9ea2037c6ff',NULL,'来源标题出现直接技术信号：营养干预；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202603/562266.shtml'),
  ('3ffece2c-59cf-5cfe-8ed4-7b813db6048e','596a5389-b98a-5194-80d4-6aab5261f7bc','cad04295-6a2f-5b45-9641-a82de5596698',NULL,'来源标题出现直接技术信号：激光；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202604/562392.shtml'),
  ('19d90326-ada2-5314-bda8-d54f1d483240','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202604/562505.shtml'),
  ('2e36a058-4788-5b23-9d10-c9f195847e93','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','16e44396-6f2a-5182-8b1e-f5ea08500c80','来源标题出现直接技术信号：复材；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202604/562862.shtml'),
  ('2b83fef4-fe77-5f3b-a07a-7a3ee2b1beda','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202604/563010.shtml'),
  ('4e34448d-e2b9-50ec-8cae-cf02088771d4','596a5389-b98a-5194-80d4-6aab5261f7bc','ab8e5e92-382f-51f1-b210-735e7c2d83cb','db7b40b2-5b6a-55ee-9002-2c280871de20','核心产品是汽车底盘执行与线控部件，不属于低空飞行器或机器人关节','https://news.pedaily.cn/202604/563310.shtml'),
  ('f9560488-7572-5ffe-8175-7da9b458a909','c0983de5-d08f-53b8-901c-d750f8e863c2','e8b25a34-17ed-592d-8e9c-a68ae97ad80c',NULL,'企业开头简介出现2次一致技术信号：机器人、关节模组；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202605/563480.shtml'),
  ('b71fb29f-63d8-5fa7-910c-f98cbdf02e1e','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'企业开头简介出现3次一致技术信号：医疗、诊疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202605/563509.shtml'),
  ('bb9e2870-d5b7-5b43-af98-879dc84c8441','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202605/564410.shtml'),
  ('5e3182f1-c265-5703-b329-1f58d8b73a11','d97f43a8-6431-53ab-8a0f-7b249293c6ec','e9970960-9052-57ec-af94-dc10cd0c7de7','3a6de858-d0ef-5a96-8c18-8640e655d4bf','产品为裂变反应堆系统，不属于聚变或一般新能源材料','https://news.pedaily.cn/202606/565117.shtml'),
  ('698380d7-9064-541a-b620-c208caec645b','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','16e44396-6f2a-5182-8b1e-f5ea08500c80','来源标题出现直接技术信号：电致变色；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202606/565410.shtml'),
  ('898c2b60-2eb6-5e81-87a2-855007055015','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202606/565537.shtml'),
  ('4a9c4de2-545b-52c6-9a22-38271b6963f2','d97f43a8-6431-53ab-8a0f-7b249293c6ec','715204f3-bd31-5370-9c1d-baf9c813364b','30e3c50c-5258-5dc6-bfce-64f0468ec7bf','聚变装置、约束路线与工程化系统构成独立技术边界','https://news.pedaily.cn/202606/565525.shtml'),
  ('661d4a4b-68c1-50e7-81e6-1b0423a2e52b','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/565727.shtml'),
  ('ef7712bf-2de6-5ecc-b7d3-34956937a0b2','c9a16792-5f10-51fb-9437-875c75b8a7f0',NULL,NULL,'来源标题出现直接技术信号：Micro-LED、光电；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/565739.shtml'),
  ('262c9fa4-446c-5d12-86af-585a957a0f48','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗、诊疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/565957.shtml'),
  ('67140669-7331-5ba7-a9da-e5e4f60221ff','c9a16792-5f10-51fb-9437-875c75b8a7f0',NULL,NULL,'企业开头简介出现3次一致技术信号：芯片、EDA；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/566078.shtml'),
  ('d9b2c09f-5bbe-5a1c-ae8b-177446aa206a','d97f43a8-6431-53ab-8a0f-7b249293c6ec','715204f3-bd31-5370-9c1d-baf9c813364b','30e3c50c-5258-5dc6-bfce-64f0468ec7bf','聚变装置、约束路线与工程化系统构成独立技术边界','https://news.pedaily.cn/202607/566073.shtml'),
  ('bd09bbeb-c517-55eb-ab47-9e5a2c8f9286','596a5389-b98a-5194-80d4-6aab5261f7bc','ea27f577-3922-5bb8-8d89-986d9b8c9887',NULL,'来源标题出现直接技术信号：试验试飞、适航认证；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/566402.shtml'),
  ('fe5f8532-170d-54a1-8575-284034325aec','d97f43a8-6431-53ab-8a0f-7b249293c6ec','e9970960-9052-57ec-af94-dc10cd0c7de7','3a6de858-d0ef-5a96-8c18-8640e655d4bf','产品为裂变反应堆系统，不属于聚变或一般新能源材料','https://news.pedaily.cn/202607/566732.shtml'),
  ('02fb4ad4-25db-52f8-b5dc-83a347366d9c','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','01057042-e097-58bf-b94d-0bc4532ba1f9','主营超导材料、带材或强场磁体可归入功能材料，聚变只是部分应用场景','https://news.pedaily.cn/202607/566927.shtml'),
  ('daac7138-bdd8-509c-b241-b9376e09c588','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','01057042-e097-58bf-b94d-0bc4532ba1f9','主营超导材料、带材或强场磁体可归入功能材料，聚变只是部分应用场景','https://news.pedaily.cn/202607/566976.shtml'),
  ('d1fd4e0b-b68d-5b53-aec6-0f8633ae4ba6','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202607/567026.shtml'),
  ('a0d34207-3e41-5f72-adc8-9788556b91ae','d97f43a8-6431-53ab-8a0f-7b249293c6ec','715204f3-bd31-5370-9c1d-baf9c813364b','30e3c50c-5258-5dc6-bfce-64f0468ec7bf','聚变装置、约束路线与工程化系统构成独立技术边界','https://news.pedaily.cn/202608/567465.shtml'),
  ('c337ad17-b5bf-5451-ad0d-e9c6f273095e','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','279e5504-daac-52ec-a56f-e3a8337ee5be','8f2b2494-d4e4-5017-9504-740ff11a9110','主营医用放射性核素或核医学服务，属于生命科学而非核能工程','https://news.pedaily.cn/202608/567611.shtml'),
  ('fef3a9e2-bd8c-5270-8a4c-08a48adf19a6','c9a16792-5f10-51fb-9437-875c75b8a7f0','23065258-afd9-5a5b-8cf8-9b763c8a5e01',NULL,'来源标题出现直接技术信号：光电；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202608/567697.shtml'),
  ('205ccb65-a770-56f2-8c73-86d094624926','596a5389-b98a-5194-80d4-6aab5261f7bc','ab8e5e92-382f-51f1-b210-735e7c2d83cb','db7b40b2-5b6a-55ee-9002-2c280871de20','核心产品是汽车底盘执行与线控部件，不属于低空飞行器或机器人关节','https://news.pedaily.cn/202608/567857.shtml'),
  ('fde8c7c9-9fda-59cb-806f-0e42b20dcdfb','d97f43a8-6431-53ab-8a0f-7b249293c6ec','924a6dff-cbc3-5f26-903c-47b714a0d79f','08909eda-98db-52d0-8225-df787f0e85fc','来源标题出现直接技术信号：涂层；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202608/567868.shtml'),
  ('6a23d405-40e6-5593-b2e0-2c46c990a9db','c9a16792-5f10-51fb-9437-875c75b8a7f0','23065258-afd9-5a5b-8cf8-9b763c8a5e01',NULL,'企业开头简介出现2次一致技术信号：半导体、EDA；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202608/568032.shtml'),
  ('1887219d-9e23-55b7-b91a-87c390f4f067','d97f43a8-6431-53ab-8a0f-7b249293c6ec','715204f3-bd31-5370-9c1d-baf9c813364b','a932adda-5b3b-552c-b63f-5309a496ec53','聚变装置、约束路线与工程化系统构成独立技术边界','https://news.pedaily.cn/202608/568139.shtml'),
  ('363a0bb4-362a-5a9a-bd72-99a828e78781','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202609/568620.shtml'),
  ('7f708578-293d-58c9-904e-079a61e42191','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','ae3ab5bf-b59e-5caf-8660-a9ea2037c6ff',NULL,'来源标题出现直接技术信号：医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202609/568859.shtml'),
  ('a7035583-b847-5690-9a7a-450e57d61ac5','d97f43a8-6431-53ab-8a0f-7b249293c6ec','edc8b06e-95f5-5d50-bc86-eaa6c90b8398','01057042-e097-58bf-b94d-0bc4532ba1f9','主营超导材料、带材或强场磁体可归入功能材料，聚变只是部分应用场景','https://news.pedaily.cn/202609/569119.shtml'),
  ('e023809e-052c-51bb-942a-8632a5def9d8','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：医疗、医用、精准给药；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202609/569556.shtml'),
  ('e523da94-658b-575b-a07a-ef72985bb2b6','c9a16792-5f10-51fb-9437-875c75b8a7f0',NULL,NULL,'来源标题出现直接技术信号：Micro LED、光电；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202610/569913.shtml'),
  ('7e9dcec0-ae16-5ef5-a0c4-1d34ecbd9ed8','596a5389-b98a-5194-80d4-6aab5261f7bc','ab8e5e92-382f-51f1-b210-735e7c2d83cb','db7b40b2-5b6a-55ee-9002-2c280871de20','核心产品是汽车底盘执行与线控部件，不属于低空飞行器或机器人关节','https://news.pedaily.cn/202610/570371.shtml'),
  ('e5a724b0-2dd8-5408-86a6-3c1af53221a1','31fc4a30-6fb7-5de4-a08f-ea66cf052e26','31fc3cbf-4043-521a-b380-b6d3f3b14dca','cd096937-b9a3-5abe-a0ee-7880fdbe62bb','产品是近眼显示与空间交互终端，现有个人AI主题未覆盖视觉空间计算','https://news.pedaily.cn/202610/570560.shtml'),
  ('952e962a-ae94-5ea5-a42e-f57f94d12aa5','8ed1f51f-0901-5b42-bac7-06ce139ce2a9','57d47879-d88d-53cf-a4ab-3a84727d9ac2',NULL,'来源标题出现直接技术信号：制药、医疗；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202610/570800.shtml'),
  ('b3e8bb1b-292d-5701-8b79-3f8f2ee0584b','31fc4a30-6fb7-5de4-a08f-ea66cf052e26','8c4dfb2c-83f9-52ec-a1c4-6d2c16f51dd9','c648613d-d0f6-513c-ba78-94dd82b7f17d','来源标题出现直接技术信号：Scaling；下级分类仅在技术边界明确时填写','https://news.pedaily.cn/202610/570816.shtml')
)
INSERT INTO v37_candidate_classifications(
  candidate_id,taxonomy_version,stable_event_id,original_industry_id,original_field_id,original_topic_id,
  suggested_industry_id,suggested_field_id,suggested_topic_id,company_evidence,source_url,mapping_basis,
  review_status,created_at,created_by
)
SELECT c.candidate_id,'V3.7',c.stable_event_id,p.existing_industry_id,p.existing_field_id,p.existing_topic_id,
       a.suggested_industry_id,a.suggested_field_id,a.suggested_topic_id,
       '主营业务：' || c.primary_business || '；核心技术：' || c.core_technology,
       a.source_url,a.mapping_basis,'pending_approval',datetime('now'),'Codex'
FROM approved a JOIN v35_historical_candidates c ON c.candidate_id=a.candidate_id
LEFT JOIN v35_classification_proposals p ON p.candidate_id=c.candidate_id;

INSERT INTO v37_taxonomy_settings
SELECT 'current_taxonomy','V3.7',datetime('now'),'Codex','User-approved V3.7 classification upgrade'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');

INSERT INTO v37_taxonomy_upgrade_actions
SELECT 'v37-upgrade-' || entity_type || '-' || entity_id,'taxonomy_preserved','V3.7',entity_type,entity_id,
       '{"taxonomy_version":"V3.2"}','{"taxonomy_version":"V3.7"}',
       'Preserved original ID and parent relationship',datetime('now'),'Codex'
FROM (
  SELECT 'industry' entity_type,industry_id entity_id FROM v30_industries WHERE taxonomy_version='V3.2'
  UNION ALL SELECT 'field',field_id FROM v30_fields WHERE taxonomy_version='V3.2'
  UNION ALL SELECT 'topic',topic_id FROM v30_topics WHERE taxonomy_version='V3.2'
);

INSERT INTO v37_taxonomy_upgrade_actions
SELECT 'v37-current-version','activate_version','V3.7','taxonomy_version','V3.7',
       '{"current":"V3.2"}','{"current":"V3.7"}','User-approved formal taxonomy upgrade',datetime('now'),'Codex'
WHERE EXISTS (SELECT 1 FROM v30_taxonomy_versions WHERE taxonomy_version='V3.7');
