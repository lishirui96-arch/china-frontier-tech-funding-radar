# 融资事件账本 V1 数据字典

Schema version：2。主键均为 UUID/稳定文本 ID；业务名称和 URL 不作为主键。时间使用 ISO 8601 文本，金额使用原币最小单位整数，不使用浮点数。

| 表 | 用途 | 关键字段与约束 |
|---|---|---|
| `schema_migrations` | 迁移历史 | 版本、文件名、SHA-256、应用时间；已应用文件变更会拒绝启动 |
| `sources` | 来源白名单 | 来源类型、来源族、默认 S/A/B/C/D、条款状态 |
| `raw_documents` | 只追加原始登记 | 原始/规范 URL、标题、日期、允许文本/摘要、哈希、引用来源、留档/相关性/审核状态；同 URL 不删除转载 |
| `companies` | 企业主体 | 官方/简称/英文名、地区、域名、集团/子公司/品牌/法人类型、标准化与人工状态、证据 |
| `company_aliases` | 企业别名 | 简称、曾用名、英文名、品牌、媒体名；置信度与人工状态 |
| `investors` | 投资主体 | 官方/简称/英文名、地区、域名、机构类型、标准化与人工状态、证据 |
| `investor_aliases` | 投资机构别名 | 含品牌和基金载体类型；置信度与人工状态 |
| `funding_events` | 唯一融资事件 | 企业、日期范围、轮次原文/标准值、金额原文/精确/上下界/币种/类型/规则/累计标记、用途、S–D、审核状态 |
| `event_documents` | 事件—文档 | `primary/supporting/duplicate_report/correction/discovered_via`；不删除原文 |
| `event_investors` | 事件—机构 | 领投、跟投、老股东追加、独家、未说明；角色原文和证据 |
| `evidence_records` | 字段级证据 | 实体、字段、原文摘录、span、S–D、核验人/时间；无证据字段必须为空 |
| `dedup_candidates` | 重复候选 | 七项特征分、强冲突、详情、总分、风险、规则版本和状态 |
| `dedup_decisions` | 人工去重决定 | 合并/不合并/补充披露/待定、理由、操作者、规则版本、当前指针和反向决定链 |
| `audit_logs` | 关键修改审计 | 操作者、动作、实体、前后 JSON、理由、规则版本、时间 |
| `releases` | 不可变发布头 | 名称、操作者、manifest、事件数、内容哈希；触发器禁止更新/删除 |
| `release_events` | 不可变发布事件 | 事件和证据 JSON 快照、稳定顺序；触发器禁止更新/删除 |
| `rule_versions` | 通用规则 | 类型、版本、JSON 定义、启用状态 |
| `amount_rule_versions` | 金额规则 | 版本、JSON 定义、启用状态 |
| `import_batches` | URL 导入批次 | 类型、提交/新增/重复/失败、错误、操作者和时间 |
| `discovery_runs` / `discovery_failures` | 低频发现 | 请求数、结果、解析器、失败、退避和下次允许时间 |
| `extraction_candidates` | 字段候选 | 原值、标准候选、字符 span、置信度、提取器和审核状态 |
| `review_rounds` | 双审 | 一审/二审、审核人、结果、发现和理由 |
| `release_status_history` | 发布状态历史 | 原/新状态、操作者、理由、时间和 audit ID |

## 审核状态

正常路径：`discovered → parsed → entity_review → dedup_review → field_review → approved → published`。旁路状态：`needs_correction`、`held`、`rejected`。任何旁路均不物理删除历史。

## 发布隔离

候选数据保存在业务表；公开/发布查询必须指定 `release_id` 并读取 `release_events` 快照。`LedgerRepository(read_only=True)` 使用 SQLite `mode=ro`，拒绝写入。

