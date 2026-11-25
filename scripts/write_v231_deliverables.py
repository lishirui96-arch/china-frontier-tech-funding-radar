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


reviews = rows("""SELECT r.*,t.candidate_name,t.technical_boundary,f.name field_name,i.name industry_name
  FROM v231_topic_admission_reviews r JOIN v22_topics t ON t.topic_id=r.source_topic_id
  JOIN v22_fields f ON f.field_id=t.field_id JOIN v22_industries i ON i.industry_id=f.industry_id
  ORDER BY i.sort_order,f.sort_order,t.candidate_name""")
members = rows("""SELECT q.*,t.candidate_name,c.display_name,p.primary_business,l.product_basis,
  l.technology_basis,l.evidence_basis,p.evidence_urls_json
  FROM v231_member_quality q JOIN v22_topics t ON t.topic_id=q.source_topic_id
  JOIN v22_companies c USING(company_id) JOIN v22_company_profiles p USING(company_id)
  JOIN v22_company_topic_links l ON l.topic_id=q.source_topic_id AND l.company_id=q.company_id
  ORDER BY t.candidate_name,c.display_name""")
entities = rows("""SELECT r.*,l.display_name left_name,rr.display_name right_name
  FROM v231_entity_reviews r JOIN v22_companies l ON l.company_id=r.left_company_id
  JOIN v22_companies rr ON rr.company_id=r.right_company_id""")
cross = rows("""SELECT r.*,c.display_name,t.candidate_name FROM v231_cross_topic_reviews r
  JOIN v22_companies c USING(company_id) JOIN v22_topics t ON t.topic_id=r.source_topic_id
  ORDER BY c.display_name,t.candidate_name""")

for member in members:
    member["quality_score"] = sum([
        member["business_assessment"] == "明确",
        member["product_assessment"] == "具体",
        member["technology_assessment"] == "具体",
        member["evidence_assessment"] == "有可追溯URL",
    ])

missing = [row for row in members if row["quality_grade"] != "A"]
topic_scores = []
for review in reviews:
    topic_members = [row for row in members if row["source_topic_id"] == review["source_topic_id"]]
    total = len(topic_members) or 1
    counts = Counter(row["quality_grade"] for row in topic_members)
    topic_scores.append({
        "source_topic_id": review["source_topic_id"],
        "candidate_name": review["candidate_name"],
        "industry_name": review["industry_name"],
        "field_name": review["field_name"],
        "member_count": len(topic_members),
        "A_count": counts.get("A", 0),
        "B_count": counts.get("B", 0),
        "C_count": counts.get("C", 0),
        "D_count": counts.get("D", 0),
        "business_clear_rate": sum(row["business_assessment"] == "明确" for row in topic_members) / total,
        "product_specific_rate": sum(row["product_assessment"] == "具体" for row in topic_members) / total,
        "technology_specific_rate": sum(row["technology_assessment"] == "具体" for row in topic_members) / total,
        "traceable_url_rate": sum(row["evidence_assessment"] == "有可追溯URL" for row in topic_members) / total,
        "admission_conclusion": review["admission_conclusion"],
        "conclusion_reason": review["conclusion_reason"],
    })
boundaries = [{key: row[key] for key in (
    "source_topic_id", "candidate_name", "industry_name", "field_name",
    "common_technology_claim", "difference_assessment", "boundary_assessment",
    "cross_topic_notes", "admission_conclusion", "conclusion_reason",
)} for row in reviews]

datasets = {
    "14主题质量评分": topic_scores,
    "重复实体核查": entities,
    "画像缺失清单": missing,
    "共同技术与边界": boundaries,
    "企业交叉标签": cross,
    "修订候选清单": reviews,
    "审查说明": [{
        "研究截止日": "2026-11-25",
        "证据口径": "沿用B级媒体融资证据；技术主题准入另需具体产品和技术依据",
        "历史保护": "V2.2/V2.3历史数据不覆盖，未提交人工裁决",
        "正式发布": "未创建Release，8511数据源未变更",
    }],
}

file_names = {
    "14主题质量评分": "V231_14_TOPIC_QUALITY_SCORES.csv",
    "重复实体核查": "V231_DUPLICATE_ENTITY_REVIEW.csv",
    "画像缺失清单": "V231_PROFILE_EVIDENCE_GAPS.csv",
    "共同技术与边界": "V231_COMMON_TECH_BOUNDARIES.csv",
    "企业交叉标签": "V231_CROSS_TOPIC_RELATIONS.csv",
    "修订候选清单": "V231_REVISED_FORMAL_TOPIC_CANDIDATES.csv",
}
for label, file_name in file_names.items():
    data = datasets[label]
    with (OUT / file_name).open("w", encoding="utf-8-sig", newline="") as handle:
        headers = list(data[0]) if data else []
        if headers:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)

conclusions = Counter(row["admission_conclusion"] for row in reviews)
grades = Counter(row["quality_grade"] for row in members)
report = [
    "# V2.3.1 主题准入质量审查报告", "",
    "本报告是独立建议层，不代表用户已确认、合并、拆分或排除任何主题或企业。", "",
    "## 审查结论", "",
    f"- 审查主题：{len(reviews)}个。",
    f"- 调整企业成员后提交确认：{sum(v for k,v in conclusions.items() if k.startswith('C.'))}个。",
    f"- 建议拆分：{sum(v for k,v in conclusions.items() if k.startswith('D.'))}个。",
    f"- 暂缓：{sum(v for k,v in conclusions.items() if k.startswith('E.'))}个。",
    f"- 企业—主题成员关系：{len(members)}条；画像等级分布：{dict(sorted(grades.items()))}。", "",
    "融资媒体链接只证明融资事实或企业方向，不能自动证明多个企业共享同一项具体技术。规则生成的通用产品、技术描述不作为正式主题准入的充分依据。", "",
    "## 14个主题逐项建议", "",
    "|产业|技术领域|主题|结论|唯一企业|唯一事件|正式/A/B|理由|", "|---|---|---|---|---:|---:|---|---|",
]
for row in reviews:
    report.append(f"|{row['industry_name']}|{row['field_name']}|{row['candidate_name']}|{row['admission_conclusion']}|{row['unique_company_count']}|{row['unique_event_count']}|{row['formal_count']}/{row['a_count']}/{row['b_count']}|{row['conclusion_reason']}|")
report += ["", "## 重复实体", ""]
for row in entities:
    report.append(f"- {row['left_name']} / {row['right_name']}：{row['recommendation']}。统一社会信用代码状态：{row['legal_identifier_status']}。")
report += ["", "## 需要用户亲自决定", "",
    "- 是否按建议从5个主题移除或暂缓证据不足的企业成员。",
    "- 是否将多路线量子计算硬件主题按硬件路线拆分。",
    "- 是否在补充产品级技术证据前继续暂缓8个主题。",
    "- 是否确认优理奇两条历史ID属于同一主体，并建立主从ID映射。",
]
(OUT / "V231_TOPIC_ADMISSION_REVIEW.md").write_text("\n".join(report) + "\n", encoding="utf-8")

(ROOT / "work" / "v231_workbook_data.json").write_text(
    json.dumps(datasets, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({"topics": len(reviews), "members": len(members), "grades": grades, "conclusions": conclusions}, ensure_ascii=False, default=dict))
connection.close()
