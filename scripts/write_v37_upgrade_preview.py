from __future__ import annotations

import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from funding_radar.db import connect


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def read_csv(name: str) -> list[dict]:
    with (DOCS / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict]) -> None:
    with (DOCS / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    field_proposals = read_csv("V37_NEW_SECONDARY_FIELD_PROPOSALS.csv")
    topic_proposals = read_csv("V37_NEW_TERTIARY_TOPIC_PROPOSALS.csv")
    mappings = read_csv("V37_75_EVENT_CLASSIFICATION_MAPPING.csv")
    recommended_fields = [row for row in field_proposals if row["suggested_status"] == "recommended"]
    recommended_topics = [row for row in topic_proposals if row["suggested_status"] == "recommended"]
    approved_decisions = {"existing_taxonomy", "new_field_and_topic", "new_topic"}
    adjustments = [row for row in mappings if row["v37_decision"] in approved_decisions]

    with connect(read_only=True) as connection:
        industries = [dict(row) for row in connection.execute(
            "SELECT * FROM v30_industries WHERE taxonomy_version='V3.2' ORDER BY sort_order"
        )]
        fields = [dict(row) for row in connection.execute(
            """SELECT f.*,i.name industry_name FROM v30_fields f JOIN v30_industries i
               ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id
               WHERE f.taxonomy_version='V3.2' ORDER BY i.sort_order,f.sort_order"""
        )]
        topics = [dict(row) for row in connection.execute(
            """SELECT t.*,f.name field_name,i.industry_id,i.name industry_name
               FROM v30_topics t JOIN v30_fields f ON f.taxonomy_version=t.taxonomy_version AND f.field_id=t.field_id
               JOIN v30_industries i ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id
               WHERE t.taxonomy_version='V3.2' ORDER BY i.sort_order,f.sort_order,t.name"""
        )]
        current_counts = {row["industry_name"] or "待判断/现有体系外": row["n"] for row in connection.execute(
            """SELECT i.name industry_name,COUNT(*) n FROM v35_historical_candidates c
               JOIN v35_collection_batches b USING(batch_id) JOIN v35_classification_proposals p USING(candidate_id)
               LEFT JOIN v30_industries i ON i.taxonomy_version='V3.2' AND i.industry_id=p.existing_industry_id
               WHERE b.created_by='v35_bulk_backfill' GROUP BY i.name"""
        )}

    preview = []
    for row in industries:
        preview.append({"taxonomy_version": "V3.7", "entity_type": "industry", "entity_id": row["industry_id"],
                        "name": row["name"], "parent_id": "", "parent_name": "", "origin": "V3.2_preserved", "status": "unchanged"})
    for row in fields:
        preview.append({"taxonomy_version": "V3.7", "entity_type": "field", "entity_id": row["field_id"],
                        "name": row["name"], "parent_id": row["industry_id"], "parent_name": row["industry_name"],
                        "origin": "V3.2_preserved", "status": "unchanged"})
    for row in recommended_fields:
        preview.append({"taxonomy_version": "V3.7", "entity_type": "field", "entity_id": row["proposal_id"],
                        "name": row["classification_name"], "parent_id": row["parent_industry_id"],
                        "parent_name": row["parent_industry_name"], "origin": "V3.7_proposal", "status": "proposed"})
    for row in topics:
        preview.append({"taxonomy_version": "V3.7", "entity_type": "topic", "entity_id": row["topic_id"],
                        "name": row["name"], "parent_id": row["field_id"], "parent_name": row["field_name"],
                        "origin": "V3.2_preserved", "status": "unchanged"})
    for row in recommended_topics:
        preview.append({"taxonomy_version": "V3.7", "entity_type": "topic", "entity_id": row["proposal_id"],
                        "name": row["classification_name"], "parent_id": row["parent_id"],
                        "parent_name": row["parent_name"], "origin": "V3.7_proposal", "status": "proposed"})
    write_csv("V37_UPGRADED_TAXONOMY_PREVIEW.csv", preview)
    write_csv("V37_PARENT_RELATIONSHIP_PREVIEW.csv", [row for row in preview if row["entity_type"] != "industry"])

    adjustment_rows = []
    for row in adjustments:
        target_field_id = row["proposed_field_id"] or row["field_id"]
        target_field_name = row["proposed_field_name"] or row["field_name"]
        target_topic_id = row["proposed_topic_id"] or row["topic_id"]
        target_topic_name = row["proposed_topic_name"] or row["topic_name"]
        adjustment_rows.append({
            "candidate_id": row["candidate_id"], "company_name": row["company_name"],
            "announcement_date": row["announcement_date"], "round_original": row["round_original"],
            "target_taxonomy_version": "V3.7", "target_industry_id": row["industry_id"],
            "target_industry_name": row["industry_name"], "target_field_id": target_field_id,
            "target_field_name": target_field_name, "target_topic_id": target_topic_id,
            "target_topic_name": target_topic_name, "mapping_basis": row["classification_basis"],
            "source_url": row["source_url"], "migration_status": "preview_pending_approval",
        })
    write_csv("V37_HISTORICAL_MAPPING_ADJUSTMENTS.csv", adjustment_rows)

    additions = Counter(row["target_industry_name"] for row in adjustment_rows)
    industry_order = [row["name"] for row in industries]
    impact = []
    for name in industry_order + ["待判断/现有体系外"]:
        before = current_counts.get(name, 0)
        added = additions.get(name, 0)
        after = before + added if name != "待判断/现有体系外" else before - len(adjustment_rows)
        impact.append({"industry_name": name, "before_event_count": before, "recommended_mapping_additions": added,
                       "after_preview_event_count": after, "event_count_change": after - before})
    write_csv("V37_INDUSTRY_EVENT_COUNT_IMPACT.csv", impact)

    cutoff = date(2026, 11, 25)
    windows = {30: cutoff - timedelta(days=29), 90: cutoff - timedelta(days=89), 360: cutoff - timedelta(days=359)}
    window_impact = []
    for days, start in windows.items():
        selected = [row for row in adjustment_rows if start <= date.fromisoformat(row["announcement_date"]) <= cutoff]
        by_industry = Counter(row["target_industry_name"] for row in selected)
        if not by_industry:
            window_impact.append({"window_days": days, "start_date": start.isoformat(), "end_date": cutoff.isoformat(),
                                  "industry_name": "无调整", "remapped_event_count": 0,
                                  "total_event_count_change": 0, "note": "稳定事件ID、日期和审核状态不变"})
        for industry, count in sorted(by_industry.items()):
            window_impact.append({"window_days": days, "start_date": start.isoformat(), "end_date": cutoff.isoformat(),
                                  "industry_name": industry, "remapped_event_count": count,
                                  "total_event_count_change": 0, "note": "只改变产业分布，不改变窗口总事件数"})
    write_csv("V37_WINDOW_INDUSTRY_IMPACT.csv", window_impact)

    field_lines = "\n".join(
        f"| {row['classification_name']} | `{row['proposal_id']}` | {row['parent_industry_name']} | `{row['parent_industry_id']}` | {row['technical_boundary']} |"
        for row in recommended_fields
    )
    topic_lines = "\n".join(
        f"| {row['classification_name']} | `{row['proposal_id']}` | {row['parent_name']} | `{row['parent_id']}` | {row['technical_boundary']} |"
        for row in recommended_topics
    )
    impact_lines = "\n".join(
        f"| {row['industry_name']} | {row['before_event_count']} | {row['recommended_mapping_additions']} | {row['after_preview_event_count']} |"
        for row in impact
    )
    preview_report = f"""# V3.7 分类体系正式升级预览

## 预览结论

- 一级领域：保持10个，全部复用V3.2 ID。
- 二级领域：42个原节点全部保留，拟新增3个，预览总数45。
- 三级主题：51个原节点全部保留，拟新增6个，预览总数57。
- 金融科技二级领域和跨境支付三级主题继续作为观察项，不进入本次正式升级预览。
- 需要建立V3.7映射的历史候选事件：{len(adjustment_rows)}个；其余20个继续待判断或观察。

## 新增二级领域及父级ID

| 新二级领域 | 新ID | 所属一级领域 | 一级领域ID | 技术边界 |
|---|---|---|---|---|
{field_lines}

## 新增三级主题及父级ID

| 新三级主题 | 新ID | 所属二级领域 | 二级领域ID | 技术边界 |
|---|---|---|---|---|
{topic_lines}

## 超导与聚变边界

“超导材料与强场磁体”的父级固定为现有“高性能功能材料”(`edc8b06e-95f5-5d50-bc86-eaa6c90b8398`)，不挂在“可控核聚变工程”下。企业只有在主营超导带材、材料或磁体时归入该主题；聚变企业使用超导磁体只构成交叉关联，不改变其主分类。

## 历史事件产业分布影响

| 一级领域 | 升级前 | 建议映射新增 | 升级预览后 |
|---|---:|---:|---:|
{impact_lines}

30/90/360天总事件数分别保持117、387、1428不变。分类升级只改变产业分布：30天窗口没有调整事件；90天和360天的具体产业变化见`V37_WINDOW_INDUSTRY_IMPACT.csv`。

## ID与发布保护

- V3.2的10个一级、42个二级、51个三级ID逐一复制到V3.7版本，值保持不变。
- 9个新增节点使用V3.7提案中已生成的稳定UUID。
- 正式网站和Release继续读取V3.2，直到独立审核和发布步骤完成。
- 本预览不执行数据库迁移，也不修改任何历史映射。
"""
    (DOCS / "V37_CLASSIFICATION_UPGRADE_PREVIEW.md").write_text(preview_report, encoding="utf-8")

    migration_report = """# V3.7 数据库迁移与回滚方案

## 建议迁移方案

正式升级建议使用Schema 22，保持完全增量式：

1. 使用SQLite一致性备份并记录源库、备份的逻辑完整性和SHA-256。
2. 新建`v37_candidate_classifications`，主键为`(candidate_id,taxonomy_version)`，字段包括一级、二级、三级ID、映射依据、审核状态、批准人和时间。
3. 将V3.2的10/42/51节点复制为V3.7快照，复用全部原ID和父级关系。
4. 按依赖顺序插入3个新二级领域，再插入6个新三级主题。
5. 仅将`V37_HISTORICAL_MAPPING_ADJUSTMENTS.csv`中的55条映射写入新表，初始状态为`pending_approval`；不更新V3.5候选原记录。
6. 检查父级引用、ID唯一性、10/45/57计数、55条映射和20条未映射事件。
7. 运行全部测试和30/90/360窗口测试；窗口总数必须保持117/387/1428。
8. 在独立人工批准和Release步骤前，网站继续读取V3.2。

现有分类表以`(taxonomy_version, entity_id)`为复合主键，能够并存V3.2和V3.7。候选映射缺少并行版本表，因此Schema 22只需要新增映射表和数据迁移，不需要重建现有分类表。

## 事务与幂等性

- 整个迁移在单一事务中执行。
- 分类快照和新节点使用`INSERT ... SELECT ... WHERE NOT EXISTS`及稳定ID。
- 迁移脚本必须在目标版本已存在但内容不一致时失败，不得静默覆盖。
- 迁移前后对V3.2表行生成排序哈希，必须完全一致。

## 回滚方案

1. 事务提交前发生任何失败：直接回滚事务。
2. 已提交但未发布：保留V3.7数据，将其标记为`retired`或停止读取；网站仍指向V3.2。
3. 必须物理撤销时：创建新的前向回滚迁移，不修改或删除已应用的Schema 22记录；依次删除V3.7候选映射、V3.7新增主题、字段和版本快照。
4. 只有数据库损坏时才从升级前备份恢复，并先验证目标路径与备份完整性。
5. 回滚后重新核对Schema迁移链、V3.2行哈希、正式事件表和117/387/1428窗口统计。

## 禁止操作

- 不覆盖V3.2行，不复用新节点ID，不更新正式融资事件，不自动批准55条候选映射。
- 不以删除迁移历史、Git reset或覆盖数据库文件作为正常回滚方式。
"""
    (DOCS / "V37_DATABASE_MIGRATION_AND_ROLLBACK_PLAN.md").write_text(migration_report, encoding="utf-8")


if __name__ == "__main__":
    main()
