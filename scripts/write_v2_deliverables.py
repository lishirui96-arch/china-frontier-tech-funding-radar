from __future__ import annotations
import csv,json,sqlite3
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"docs"; OUT.mkdir(exist_ok=True)
db=sqlite3.connect(database_path());db.row_factory=sqlite3.Row
queries={
"企业技术画像":"select * from v2_company_profiles order by company_name",
"一级产业分类":"select * from v2_industry_directions order by sort_order",
"二级技术领域":"select * from v2_technology_fields order by industry_id,name",
"候选技术主题":"select * from v2_candidate_topics order by industry_id,candidate_name",
"企业主题关联":"select l.*,p.company_name,t.candidate_name from v2_company_topic_links l join v2_company_profiles p using(profile_id) join v2_candidate_topics t using(topic_id) order by t.candidate_name,p.company_name",
"事件主题关联":"select e.*,t.candidate_name from v2_event_topic_links e join v2_candidate_topics t using(topic_id) order by disclosure_date desc,company_name",
"主题重要性":"""select t.topic_id,t.candidate_name,i.name industry,f.name field,t.topic_kind,t.review_status,
count(distinct l.profile_id) companies,count(distinct e.event_ref) events,
count(distinct case when e.event_source_type='formal' then e.event_ref end) formal_events,
count(distinct case when e.event_source_type='A_candidate' then e.event_ref end) a_candidates,
count(distinct case when e.event_source_type='B_candidate' then e.event_ref end) b_candidates,
group_concat(distinct e.round_original) rounds,group_concat(distinct p.company_name) company_names
from v2_candidate_topics t join v2_industry_directions i using(industry_id) join v2_technology_fields f using(field_id)
left join v2_company_topic_links l using(topic_id) left join v2_company_profiles p using(profile_id)
left join v2_event_topic_links e using(topic_id) group by t.topic_id order by companies desc,events desc"""}
data={name:[dict(r) for r in db.execute(sql)] for name,sql in queries.items()}
for name,rows in list(data.items())[:6]:
    path=OUT/("V2_"+name+".csv")
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        if rows: w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
wb=Workbook();wb.remove(wb.active)
for name,rows in data.items():
    ws=wb.create_sheet(name[:31]); headers=list(rows[0]) if rows else ["无数据"] ;ws.append(headers)
    for row in rows: ws.append([row[h] for h in headers])
    for c in ws[1]: c.font=Font(bold=True,color="FFFFFF");c.fill=PatternFill("solid",fgColor="1F4E78")
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for idx,col in enumerate(ws.columns,1):
        width=min(48,max(10,max(len(str(x.value or "")) for x in col)+2));ws.column_dimensions[get_column_letter(idx)].width=width
        for cell in col: cell.alignment=Alignment(vertical="top",wrap_text=True)
xlsx=OUT/"NOVEMBER_2026_TECH_FINANCING_THEME_RESEARCH_V2_0.xlsx";wb.save(xlsx)
check=load_workbook(xlsx,read_only=False,data_only=False);assert len(check.sheetnames)==7
assert not any(isinstance(c.value,str) and c.value.startswith(("#REF!","#VALUE!","#DIV/0!","#NAME?")) for ws in check for row in ws for c in row);check.close()
topics=data["主题重要性"]
report=OUT/"V2_THEME_IMPORTANCE_ANALYSIS.md"
lines=["# V2.0 科技融资候选主题重要性分析","","主题为候选研究分组，不代表人工定稿。排序综合企业与事件覆盖；模糊金额和未披露金额不进入精确金额排名。","", "|候选主题|产业方向|企业|事件|正式|A类|B类|轮次|", "|---|---|---:|---:|---:|---:|---:|---|"]
for r in topics: lines.append(f"|{r['candidate_name']}|{r['industry']}|{r['companies']}|{r['events']}|{r['formal_events']}|{r['a_candidates']}|{r['b_candidates']}|{r['rounds'] or '—'}|")
report.write_text("\n".join(lines)+"\n",encoding="utf-8")
print(json.dumps({"xlsx":str(xlsx),"sheets":7,"topics":len(topics),"profiles":len(data['企业技术画像'])},ensure_ascii=False));db.close()
