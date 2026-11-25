from __future__ import annotations
import csv,json,sqlite3
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
from funding_radar.db import database_path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"docs";OUT.mkdir(exist_ok=True)
c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row
def rows(sql,args=()):return [dict(x) for x in c.execute(sql,args)]
cards=rows("""select c.*,t.candidate_name,t.technical_boundary,i.name industry_name,f.name field_name,
count(distinct l.company_id) company_count,count(distinct et.event_id) event_count,
count(distinct case when e.data_status='formal' then e.event_id end) formal_count,
count(distinct case when e.data_status='A_candidate' then e.event_id end) a_count,
count(distinct case when e.data_status='B_candidate' then e.event_id end) b_count
from v23_review_cards c join v22_topics t on t.topic_id=c.source_topic_id join v22_fields f using(field_id) join v22_industries i using(industry_id)
left join v22_company_topic_links l on l.topic_id=t.topic_id left join v22_event_topics et on et.topic_id=t.topic_id left join v22_events e using(event_id)
group by c.card_id order by i.sort_order,f.sort_order,t.candidate_name""")
merges=rows("""select p.preview_id,p.left_topic_id,l.candidate_name left_name,p.right_topic_id,r.candidate_name right_name,p.proposed_name,p.merged_company_count,p.merged_event_count,p.difference_json,p.review_status
from v23_merge_previews p join v22_topics l on l.topic_id=p.left_topic_id join v22_topics r on r.topic_id=p.right_topic_id order by p.proposed_name""")
multi=[x for x in cards if x["candidate_class"]=="A_multi_company_proposed"]
observations=[x for x in cards if x["candidate_class"]=="B_observation"]
split=[x for x in cards if x["candidate_class"]=="C_needs_further_split"]
directory=rows("""select t.*,i.name industry_name,f.name field_name,group_concat(s.source_topic_id) source_topic_ids from v23_formal_topics t join v22_fields f using(field_id) join v22_industries i using(industry_id) left join v23_formal_topic_sources s using(formal_topic_id) where t.is_active=1 group by t.formal_topic_id""")
actions=rows("select * from v23_adjudications order by occurred_at")
workbook={"34候选主题裁决":cards,"两组合并预览":merges,"23多企业审核":multi,"10观察项审核":observations,"待拆分主题":split,"正式主题目录":directory,"裁决操作记录":actions}
empty_headers={"正式主题目录":["formal_topic_id","field_id","formal_name","topic_class","technical_boundary","review_status","confirmed_by","confirmed_at","is_active","industry_name","field_name","source_topic_ids"],"裁决操作记录":["adjudication_id","source_topic_id","result_topic_id","decision","actor","before_json","after_json","reason","occurred_at"]}
for name,data in workbook.items():
    with (OUT/f"V23_{name}.csv").open("w",encoding="utf-8-sig",newline="") as f:
        heads=list(data[0]) if data else empty_headers.get(name,[])
        if heads:w=csv.DictWriter(f,fieldnames=heads);w.writeheader();w.writerows(data)
recommendations={r["recommendation"]:r["n"] for r in c.execute("select recommendation,count(*) n from v23_review_cards group by recommendation")}
report=["# V2.3 主题人工裁决准备报告","","本报告提供审核建议，不代表用户已经提交裁决。正式主题目录当前为空。","",f"- 来源候选主题：{len(cards)}",f"- 多企业主题审核卡：{len(multi)}",f"- 单企业观察项：{len(observations)}",f"- 待进一步拆分：{len(split)}",f"- 合并预览：{len(merges)}",f"- 正式目录：{len(directory)}","","## 建议分布",""]
report += [f"- {k}：{v}" for k,v in recommendations.items()]
report += ["","## 34条候选主题建议","","|产业|领域|主题|当前状态|审核建议|企业|事件|正式/A/B|","|---|---|---|---|---|---:|---:|---|"]
for x in cards:report.append(f"|{x['industry_name']}|{x['field_name']}|{x['candidate_name']}|{x['candidate_class']}|{x['recommendation']}|{x['company_count']}|{x['event_count']}|{x['formal_count']}/{x['a_count']}/{x['b_count']}|")
report += ["","## 合并预览","","合并预览按唯一企业ID和唯一事件ID去重，仅供人工确认。"]
for x in merges:report.append(f"- {x['left_name']} + {x['right_name']} → {x['proposed_name']}：{x['merged_company_count']}家企业，{x['merged_event_count']}个事件。差异：{x['difference_json']}")
(OUT/"V23_TOPIC_ADJUDICATION_REPORT.md").write_text("\n".join(report)+"\n",encoding="utf-8")
multi_md=["# V2.3 多企业主题审核卡",""]
for x in multi:
    multi_md += [f"## {x['candidate_name']}","",f"- 层级：{x['industry_name']} / {x['field_name']}",f"- 建议：{x['recommendation']}。{x['recommendation_reason']}",f"- 共同技术：{x['common_technology']}",f"- 独立研究价值：{x['independent_value']}",f"- 重复：{x['duplicate_note']}",f"- 企业/事件：{x['company_count']}/{x['event_count']}；正式/A/B：{x['formal_count']}/{x['a_count']}/{x['b_count']}","",json.dumps(json.loads(x['member_details_json']),ensure_ascii=False,indent=2),""]
(OUT/"V23_MULTI_COMPANY_REVIEW_CARDS.md").write_text("\n".join(multi_md),encoding="utf-8")
obs_md=["# V2.3 单企业观察项审核",""]
for x in observations:obs_md += [f"## {x['candidate_name']}","",f"- 建议：{x['recommendation']}。{x['recommendation_reason']}",f"- 技术边界：{x['technical_boundary']}",json.dumps(json.loads(x['member_details_json']),ensure_ascii=False,indent=2),""]
(OUT/"V23_SINGLE_COMPANY_OBSERVATIONS.md").write_text("\n".join(obs_md),encoding="utf-8")
split_md=["# V2.3 其他功能材料拆分复核",""]
for x in split:split_md += [f"## {x['candidate_name']}","",f"- 建议：{x['recommendation']}。{x['recommendation_reason']}",f"- 共同技术：{x['common_technology']}",json.dumps(json.loads(x['member_details_json']),ensure_ascii=False,indent=2),""]
(OUT/"V23_FUNCTIONAL_MATERIALS_SPLIT.md").write_text("\n".join(split_md),encoding="utf-8")
wb=Workbook();wb.remove(wb.active)
for name,data in workbook.items():
    ws=wb.create_sheet(name[:31]);heads=list(data[0]) if data else empty_headers.get(name,["无数据"]);ws.append(heads)
    for item in data:ws.append([item[h] if not isinstance(item[h],(dict,list)) else json.dumps(item[h],ensure_ascii=False) for h in heads])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="1F4E78")
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for idx,col in enumerate(ws.columns,1):
        ws.column_dimensions[get_column_letter(idx)].width=min(52,max(10,max(len(str(x.value or "")) for x in col)+2))
        for cell in col:cell.alignment=Alignment(vertical="top",wrap_text=True)
xlsx=OUT/"NOVEMBER_2026_TOPIC_ADJUDICATION_V2_3.xlsx";wb.save(xlsx);check=load_workbook(xlsx,read_only=False);assert len(check.sheetnames)==7;check.close()
print(json.dumps({"cards":len(cards),"multi":len(multi),"observations":len(observations),"split":len(split),"merges":len(merges),"formal":len(directory),"recommendations":recommendations,"xlsx":str(xlsx)},ensure_ascii=False));c.close()
