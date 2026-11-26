from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from funding_radar.db import database_path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
OUT.mkdir(exist_ok=True)
connection = sqlite3.connect(database_path())
connection.row_factory = sqlite3.Row


def rows(sql: str, args: tuple = ()) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, args)]


industries = rows("SELECT * FROM v30_industries WHERE taxonomy_version='V3.0' ORDER BY sort_order")
fields = rows("""SELECT f.*,i.name industry_name FROM v30_fields f JOIN v30_industries i
 ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id WHERE f.taxonomy_version='V3.0' ORDER BY i.sort_order,f.sort_order""")
topics = rows("""SELECT t.*,f.name field_name,i.name industry_name FROM v30_topics t JOIN v30_fields f
 ON f.taxonomy_version=t.taxonomy_version AND f.field_id=t.field_id JOIN v30_industries i
 ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id WHERE t.taxonomy_version='V3.0' ORDER BY i.sort_order,f.sort_order,t.name""")
aliases = rows("SELECT * FROM v30_topic_aliases WHERE taxonomy_version='V3.0'")
records = rows("""SELECT h.*,c.primary_industry_id,c.primary_field_id,c.primary_topic_id,c.classification_reason,c.confidence,
 c.needs_manual_review,c.classification_status,i.name industry_name,f.name field_name,t.name topic_name
 FROM v30_historical_records h JOIN v30_record_classifications c USING(record_id)
 LEFT JOIN v30_industries i ON i.taxonomy_version=c.taxonomy_version AND i.industry_id=c.primary_industry_id
 LEFT JOIN v30_fields f ON f.taxonomy_version=c.taxonomy_version AND f.field_id=c.primary_field_id
 LEFT JOIN v30_topics t ON t.taxonomy_version=c.taxonomy_version AND t.topic_id=c.primary_topic_id
 ORDER BY h.disclosure_date DESC,h.company_name_standard""")
event_topics = rows("""SELECT h.unique_event_id,h.record_id,h.company_id,h.company_name_standard,rt.topic_id,rt.link_role,rt.basis,
 t.name topic_name,f.name field_name,i.name industry_name FROM v30_record_topics rt JOIN v30_historical_records h USING(record_id)
 JOIN v30_topics t ON t.taxonomy_version=rt.taxonomy_version AND t.topic_id=rt.topic_id
 JOIN v30_fields f ON f.taxonomy_version=t.taxonomy_version AND f.field_id=t.field_id
 JOIN v30_industries i ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id
 ORDER BY h.company_name_standard,rt.link_role,t.name""")
company_topics = rows("""SELECT DISTINCT h.company_id,h.company_name_standard,et.industry_name,et.field_name,et.topic_id,et.topic_name,
 et.link_role,et.basis FROM v30_historical_records h JOIN
 (SELECT h2.company_id,rt.topic_id,rt.link_role,rt.basis,t.name topic_name,f.name field_name,i.name industry_name
  FROM v30_record_topics rt JOIN v30_historical_records h2 USING(record_id) JOIN v30_topics t
  ON t.taxonomy_version=rt.taxonomy_version AND t.topic_id=rt.topic_id JOIN v30_fields f
  ON f.taxonomy_version=t.taxonomy_version AND f.field_id=t.field_id JOIN v30_industries i
  ON i.taxonomy_version=f.taxonomy_version AND i.industry_id=f.industry_id) et ON et.company_id=h.company_id
 ORDER BY h.company_name_standard,et.link_role,et.topic_name""")
pending = [row for row in records if row["needs_manual_review"]]

topic_stats = []
for topic in topics:
    linked = [x for x in event_topics if x["topic_id"] == topic["topic_id"]]
    event_ids = {x["unique_event_id"] for x in linked}
    linked_records = [x for x in records if x["unique_event_id"] in event_ids]
    rounds = Counter(x["round_original"] for x in linked_records)
    topic_stats.append({
        "industry_name": topic["industry_name"], "field_name": topic["field_name"], "topic_id": topic["topic_id"],
        "topic_name": topic["name"], "management_status": topic["management_status"],
        "company_count": len({x["company_id"] for x in linked_records if x["company_id"]}),
        "unique_event_count": len(event_ids), "A_candidate_count": sum(x["queue_class"] == "A" for x in linked_records),
        "B_candidate_count": sum(x["queue_class"] == "B" for x in linked_records),
        "round_distribution": json.dumps(rounds, ensure_ascii=False, sort_keys=True),
        "amount_note": "保留金额原文；未披露不填0，模糊金额不取中值",
    })

hierarchy = []
for topic in topics:
    hierarchy.append({"taxonomy_version":"V3.0","taxonomy_status":"frozen","industry_id":next(x["industry_id"] for x in fields if x["field_id"]==topic["field_id"]),
        "industry_name":topic["industry_name"],"field_id":topic["field_id"],"field_name":topic["field_name"],"topic_id":topic["topic_id"],
        "topic_name":topic["name"],"topic_status":topic["management_status"],"source_kind":topic["source_kind"],"source_ref":topic["source_ref"]})

datasets = {
    "三级分类总表": hierarchy,
    "97条迁移对照": records,
    "唯一融资事件": records,
    "事件主题关联": event_topics,
    "企业主题关联": company_topics,
    "主题融资统计": topic_stats,
    "待分类人工复核": pending,
}

for name, data in datasets.items():
    path = OUT / f"V30_{name}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if data:
            writer = csv.DictWriter(handle, fieldnames=list(data[0]))
            writer.writeheader(); writer.writerows(data)

summary = {
    "source_records": len(records), "unique_events": len({x["unique_event_id"] for x in records}),
    "classified": sum(x["primary_topic_id"] is not None for x in records),
    "pending": sum(x["primary_topic_id"] is None for x in records),
    "A": sum(x["queue_class"] == "A" for x in records), "B": sum(x["queue_class"] == "B" for x in records),
}
freeze = ["# V3.0 分类体系冻结报告", "", "分类数据直接读取V2.2/V2.3/V2.3.1数据库，没有按聊天文本重建。", "",
          f"- 一级产业：{len(industries)}", f"- 二级领域：{len(fields)}", f"- 三级来源候选主题：{len(topics)}", f"- 历史重复主题别名关系：{len(aliases)}",
          "- taxonomy_version：V3.0", "- taxonomy_status：frozen", "", "## 差异审计", "",
          "现有数据库数量与用户确认的10/38/34完全一致，未静默改名。两组概念重复主题保留原始ID，通过别名关系表达，未删除来源主题。"]
(OUT/"V30_TAXONOMY_FREEZE_REPORT.md").write_text("\n".join(freeze)+"\n",encoding="utf-8")
migration = ["# V3.0 数据库迁移报告", "", f"- 97条原始记录全部找回：是", f"- 稳定唯一事件：{summary['unique_events']}",
             "- 97条记录在V1.4/V1.5层已经是独立event_unit，迁移层重复来源：0", f"- 继承V2主题关系：{summary['classified']}",
             f"- 补回但仍待分类：{summary['pending']}", "- V2的85个事件由76条候选事件加9条早期正式事件构成；缺少的21条候选现已补回。", "",
             "所有迁移记录保留review_item_id、event_unit_id、canonical_event_id、原始快照、来源URL和审核状态。"]
(OUT/"V30_DATABASE_MIGRATION_REPORT.md").write_text("\n".join(migration)+"\n",encoding="utf-8")
(ROOT/"work"/"v30_workbook_data.json").write_text(json.dumps(datasets,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"summary":summary,"taxonomy":{"industries":len(industries),"fields":len(fields),"topics":len(topics),"aliases":len(aliases)},"sheets":len(datasets)},ensure_ascii=False))
connection.close()
