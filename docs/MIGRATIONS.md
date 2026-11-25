# 迁移说明

`migrations/001_initial.sql` 建立 V1 的 18 张业务/审计表、索引和不可变触发器。`funding_radar.migrations.migrate()` 按三位数字文件名前缀顺序执行：

`migrations/003_november_sample_library.sql` 新增月度融资样本画像、独立并购事件、企业技术画像、六大产业分类、技术关键词、候选主题及人工调整历史。迁移只增加表和索引，不删除或覆盖已有数据。

1. 先创建迁移登记表；
2. 读取已应用版本和校验和；
3. 未应用迁移在事务中执行；
4. 已应用迁移只校验 SHA-256，不重复执行；
5. 已应用 SQL 被修改时立即失败，要求创建下一序号迁移。

运行：`.\.venv\Scripts\python -m scripts.migrate`。

SQLite 连接统一开启 `foreign_keys`、WAL、30 秒 `busy_timeout` 和 `synchronous=NORMAL`。未来迁移 PostgreSQL 时保留 UUID、关联表、整数金额和 Repository 接口；不要把 SQLite JSON 或 FTS 作为核心关系。

