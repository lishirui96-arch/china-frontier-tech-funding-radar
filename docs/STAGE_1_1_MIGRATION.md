# Schema V2 迁移说明

`002_stage_1_1.sql` 只追加结构，不修改 `001_initial.sql`。

扩展 `sources`：启用状态、允许访问范围、最小间隔、最近抓取、失败数。扩展 `raw_documents`：域名、抓取状态、10 类融资初筛、事件关联状态和导入时间。

新增：

- `import_batches`：单条/批量/CSV/手工导入统计。
- `discovery_runs`、`discovery_failures`：低频发现、请求预算、退避和失败。
- `extraction_candidates`：字段值、标准候选、字符 span、置信度、版本和审核状态。
- `review_rounds`：同一实体的一审/二审及分歧。
- `release_status_history`：Release 状态追加历史，关联审计日志。

迁移重复执行安全；已应用 SQL 校验和变化会失败。开发数据库已迁移至 V2。

