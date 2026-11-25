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
industries=rows("select * from v22_industries order by sort_order")
fields=rows("select f.*,i.code industry_code,i.name industry_name from v22_fields f join v22_industries i using(industry_id) order by i.sort_order,f.sort_order")
topics=rows("""select t.*,f.name field_name,i.code industry_code,i.name industry_name,
count(distinct l.company_id) company_count,count(distinct et.event_id) event_count,
count(distinct case when e.data_status='formal' then e.event_id end) formal_count,
count(distinct case when e.data_status='A_candidate' then e.event_id end) a_count,
count(distinct case when e.data_status='B_candidate' then e.event_id end) b_count,group_concat(distinct cp.display_name) companies
from v22_topics t join v22_fields f using(field_id) join v22_industries i using(industry_id)
left join v22_company_topic_links l using(topic_id) left join v22_companies cp using(company_id)
left join v22_event_topics et using(topic_id) left join v22_events e using(event_id)
group by t.topic_id order by i.sort_order,f.sort_order,t.candidate_name""")
companies=rows("""select c.company_id,c.display_name,c.entity_status,p.primary_business,p.core_products,p.core_technologies,p.application_scenarios,p.value_chain_position,p.classification_status,p.classification_reason,
i.name primary_industry,f.name primary_field,t.candidate_name primary_topic,group_concat(distinct x.candidate_name) linked_topics,group_concat(distinct g.tag) auxiliary_tags
from v22_companies c join v22_company_profiles p using(company_id) left join v22_industries i on i.industry_id=p.primary_industry_id
left join v22_fields f on f.field_id=p.primary_field_id left join v22_topics t on t.topic_id=p.primary_topic_id
left join v22_company_topic_links l using(company_id) left join v22_topics x on x.topic_id=l.topic_id left join v22_company_tags g using(company_id)
group by c.company_id order by p.classification_status,c.display_name""")
triage=rows("""select p.company_name,x.suggested_disposition,x.suggested_industry,x.suggested_field,x.suggested_topic,x.evidence_assessment,x.rationale,
v.classification_status,i.name v22_industry,f.name v22_field,t.candidate_name v22_topic
from v21_profile_triage x join v2_company_profiles p using(profile_id) join v22_companies c on c.source_profile_id=p.profile_id
join v22_company_profiles v using(company_id) left join v22_industries i on i.industry_id=v.primary_industry_id
left join v22_fields f on f.field_id=v.primary_field_id left join v22_topics t on t.topic_id=v.primary_topic_id order by p.company_name""")
cross=rows("""select c.company_id,c.display_name,t.candidate_name,l.link_role,l.product_basis,l.technology_basis
from v22_company_topic_links l join v22_companies c using(company_id) join v22_topics t using(topic_id)
where c.company_id in (select company_id from v22_company_topic_links group by company_id having count(*)>1)
order by c.display_name,t.candidate_name""")
relations=rows("""select r.*,l.candidate_name left_name,x.candidate_name right_name from v22_topic_relations r join v22_topics l on l.topic_id=r.left_topic_id join v22_topics x on x.topic_id=r.right_topic_id""")
history=rows("select * from v22_topic_history order by occurred_at")
observations=[x for x in topics if x["management_status"]=="B_observation"]
needs_split=[x for x in topics if x["management_status"]=="C_needs_further_split"]
workbook={"一级产业导航":industries,"二级技术领域":fields,"三级候选主题":topics,"企业归属":companies,"单企业观察项":observations,"待进一步拆分":needs_split,"企业交叉标签":cross}
exports={**workbook,"53家待处理企业":triage,"主题重复冲突":relations,"主题调整历史":history}
empty_headers={"主题调整历史":["history_id","topic_id","action_type","actor","before_json","after_json","reason","occurred_at"]}
for name,data in exports.items():
    with (OUT/f"V22_{name}.csv").open("w",encoding="utf-8-sig",newline="") as f:
        heads=list(data[0]) if data else empty_headers.get(name,[])
        if heads:w=csv.DictWriter(f,fieldnames=heads);w.writeheader();w.writerows(data)
status={r["management_status"]:r["n"] for r in c.execute("select management_status,count(*) n from v22_topics group by management_status")}
classified={r["classification_status"]:r["n"] for r in c.execute("select classification_status,count(*) n from v22_company_profiles group by classification_status")}
triage_classified=sum(x["classification_status"]=="classified_proposed" for x in triage)
report=["# V2.2 三级产业技术分类体系审计报告","","V2.2是独立建议层。一级导航由用户确认；三级主题状态仍等待人工审核，不进入8511正式导航。","",f"- 一级产业导航：{len(industries)}",f"- 二级技术领域：{len(fields)}",f"- 历史来源候选主题：{len(topics)}",f"- 多企业候选：{status.get('A_multi_company_proposed',0)}",f"- 单企业观察项：{status.get('B_observation',0)}",f"- 待进一步拆分：{status.get('C_needs_further_split',0)}",f"- 企业交叉标签涉及企业：{len(set(x['company_id'] for x in cross))}",f"- 123份画像已提出主分类：{classified.get('classified_proposed',0)}",f"- 仍未分类：{classified.get('unclassified',0)}",f"- 53家待处理企业已提出主分类：{triage_classified}","","## 34条来源候选归属","","|一级产业|二级领域|三级候选主题|状态|企业|事件|正式/A/B|", "|---|---|---|---|---:|---:|---|"]
for x in topics:report.append(f"|{x['industry_name']}|{x['field_name']}|{x['candidate_name']}|{x['management_status']}|{x['company_count']}|{x['event_count']}|{x['formal_count']}/{x['a_count']}/{x['b_count']}|")
report += ["","## 数量差异与重复","","历史结构确有14个保留来源主题和20个拆分来源子组，共34条来源候选。用户指令逐项列出的框架为32个名称。V2.2识别出两组概念重复，因此没有补造额外主题："]
for x in relations:report.append(f"- {x['left_name']} ↔ {x['right_name']}：{x['recommendation']}。{x['reason']}")
report += ["","## 无企业主题","","半导体装备与先进封装等二级领域已经建立，但没有为了填满导航强行生成三级主题。"]
(OUT/"V22_TAXONOMY_AUDIT_REPORT.md").write_text("\n".join(report)+"\n",encoding="utf-8")
wb=Workbook();wb.remove(wb.active)
for name,data in workbook.items():
    ws=wb.create_sheet(name[:31]);heads=list(data[0]) if data else ["无数据"];ws.append(heads)
    for item in data:ws.append([item[h] if not isinstance(item[h],(dict,list)) else json.dumps(item[h],ensure_ascii=False) for h in heads])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="1F4E78")
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for idx,col in enumerate(ws.columns,1):
        ws.column_dimensions[get_column_letter(idx)].width=min(52,max(10,max(len(str(x.value or "")) for x in col)+2))
        for cell in col:cell.alignment=Alignment(vertical="top",wrap_text=True)
xlsx=OUT/"NOVEMBER_2026_THREE_LEVEL_TAXONOMY_V2_2.xlsx";wb.save(xlsx);check=load_workbook(xlsx,read_only=False);assert len(check.sheetnames)==7;check.close()
print(json.dumps({"industries":len(industries),"fields":len(fields),"topics":len(topics),"status":status,"classified":classified,"triage_classified":triage_classified,"cross_companies":len(set(x['company_id'] for x in cross)),"xlsx":str(xlsx)},ensure_ascii=False));c.close()
