# 数据库完整性报告

开发库 Schema V2，共 24 张非 SQLite 内部表。最终验收结果：`PRAGMA integrity_check = ok`，`PRAGMA foreign_key_check` 为 0 条违规。Release 内容表仍由不可变触发器保护；撤回只写 `release_status_history`。

当前真实数据：原始文档 0、融资事件 0、黄金样本 0。V2 迁移没有删除 V1 表、记录或规则。
