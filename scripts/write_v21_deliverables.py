from __future__ import annotations
import csv,json,sqlite3
from collections import Counter
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"docs";OUT.mkdir(exist_ok=True)
c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row
def rows(sql,args=()): return [dict(x) for x in c.execute(sql,args)]
audits=rows("select a.*,t.candidate_name,i.name industry_name,f.name field_name from v21_topic_audits a join v2_candidate_topics t using(topic_id) join v2_industry_directions i using(industry_id) join v2_technology_fields f using(field_id) order by i.sort_order,t.candidate_name")
overlaps=rows("select o.*,l.candidate_name left_name,r.candidate_name right_name from v21_topic_overlaps o join v2_candidate_topics l on l.topic_id=o.left_topic_id join v2_candidate_topics r on r.topic_id=o.right_topic_id order by shared_company_count desc,jaccard desc")
taxonomy=rows("select * from v21_taxonomy_proposals order by level,proposal_type")
triage=rows("select x.*,p.company_name,p.primary_business,p.core_products,p.core_technologies,p.application_scenarios,p.value_chain_position from v21_profile_triage x join v2_company_profiles p using(profile_id) order by p.company_name")
pending=[x for x in triage if x["was_pending"]];other=[x for x in triage if x["was_other"]]
cards=[];importance=[]
md=["# V2.1 候选技术主题质量审查","","本报告仅给出调整建议，不代表主题已经人工确认。","",f"- 待补充画像：{len(pending)}份",f"- 其他方向画像：{len(other)}份",f"- 两组重叠：{sum(x['was_pending'] and x['was_other'] for x in triage)}份",f"- 合并去重后：{len(triage)}份",""]
for a in audits:
    members=json.loads(a["member_review_json"]);events=rows("select * from v2_event_topic_links where topic_id=? order by disclosure_date",(a["topic_id"],));statuses=Counter(x["event_source_type"] for x in events);rounds=Counter(x["round_original"] for x in events)
    keyword_sets=[]
    for p in rows("select p.keywords_json from v2_company_topic_links l join v2_company_profiles p using(profile_id) where l.topic_id=? and l.is_current=1",(a["topic_id"],)):
        try: keyword_sets.append(set(json.loads(p["keywords_json"] or "[]")))
        except json.JSONDecodeError: keyword_sets.append(set())
    kw=Counter(k for s in keyword_sets for k in s);pairs=[len(x&y)/len(x|y) for i,x in enumerate(keyword_sets) for y in keyword_sets[i+1:] if x|y];similarity=round(sum(pairs)/len(pairs),3) if pairs else None
    importance.append({"主题":a["candidate_name"],"企业数":len(members),"事件数":len(events),"正式":statuses["formal"],"A类":statuses["A_candidate"],"B类":statuses["B_candidate"],"轮次分布":json.dumps(rounds,ensure_ascii=False),"披露金额原文":"；".join(sorted({x['amount_original'] for x in events if x['amount_original'] not in ('','未披露')})),"投资机构参与":"现有V2主题关联表未结构化保存，待补充","高频关键词":"、".join(k for k,n in kw.most_common(6)),"关键词相似度":similarity,"产业链关联":"按成员产业链位置人工复核","排名范围":"单企业观察项不参与" if len(members)==1 else "多企业主题"})
    md += [f"## {a['candidate_name']}","",f"- 当前层级：{a['industry_name']} / {a['field_name']}",f"- 企业：{len(members)}；事件：{len(events)}；正式/A/B：{statuses['formal']}/{statuses['A_candidate']}/{statuses['B_candidate']}",f"- 当前边界判断：{a['boundary_assessment']}",f"- 审核建议：{a['recommendation']}",f"- 建议名称：{a['suggested_name'] or '保持当前候选名称'}",f"- 建议归属：{a['suggested_industry'] or a['industry_name']} / {a['suggested_field'] or a['field_name']}",f"- 理由：{a['recommendation_reason']}",f"- 问题：{'；'.join(json.loads(a['problems_json'])) or '未发现立即处理项'}","","|企业|主营业务|核心产品|核心技术|匹配判断|","|---|---|---|---|---|"]
    for m in members: md.append("|"+"|".join(str(m.get(k) or "—").replace("|","/") for k in ("company","business","products","technologies","fit"))+"|")
    md.append("")
    cards.extend({"主题":a["candidate_name"],"产业":a["industry_name"],"领域":a["field_name"],"建议":a["recommendation"],"建议名称":a["suggested_name"],"企业":m["company"],"主营业务":m["business"],"核心产品":m["products"],"核心技术":m["technologies"],"匹配判断":m["fit"],"事件数":len(events),"正式":statuses["formal"],"A类":statuses["A_candidate"],"B类":statuses["B_candidate"],"理由":a["recommendation_reason"]} for m in members)
(OUT/"V21_TOPIC_QUALITY_AUDIT.md").write_text("\n".join(md),encoding="utf-8")
datasets={"主题审核卡":cards,"重叠矩阵":overlaps,"三级分类建议":taxonomy,"待补充画像":pending,"其他方向画像":other,"主题调整建议":[{"主题":a["candidate_name"],"建议":a["recommendation"],"建议名称":a["suggested_name"],"建议产业":a["suggested_industry"],"建议领域":a["suggested_field"],"理由":a["recommendation_reason"]} for a in audits],"主题重要性":importance}
for name,data in datasets.items():
    with (OUT/f"V21_{name}.csv").open("w",encoding="utf-8-sig",newline="") as f:
        if data: w=csv.DictWriter(f,fieldnames=data[0].keys());w.writeheader();w.writerows(data)
report=["# V2.1 主题重要性分析","","单企业观察项不参与多企业主题排名。B类事件单列。金额保留原文；模糊金额不参与精确金额排序。投资机构尚未在V2主题关联表结构化保存，因此本版不虚构机构指标。","","|主题|企业|事件|正式|A类|B类|轮次|关键词相似度|","|---|---:|---:|---:|---:|---:|---|---:|"]
for x in sorted(importance,key=lambda z:(z["排名范围"]!="多企业主题",-z["企业数"],-z["事件数"])): report.append(f"|{x['主题']}|{x['企业数']}|{x['事件数']}|{x['正式']}|{x['A类']}|{x['B类']}|{x['轮次分布']}|{x['关键词相似度'] if x['关键词相似度'] is not None else '—'}|")
(OUT/"V21_THEME_IMPORTANCE_ANALYSIS.md").write_text("\n".join(report)+"\n",encoding="utf-8")
wb=Workbook();wb.remove(wb.active)
for name,data in datasets.items():
    ws=wb.create_sheet(name[:31]);heads=list(data[0]) if data else ["无数据"];ws.append(heads)
    for item in data: ws.append([item[h] if not isinstance(item[h],(dict,list)) else json.dumps(item[h],ensure_ascii=False) for h in heads])
    for cell in ws[1]: cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="1F4E78")
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for idx,col in enumerate(ws.columns,1):
        ws.column_dimensions[get_column_letter(idx)].width=min(50,max(10,max(len(str(x.value or "")) for x in col)+2))
        for cell in col: cell.alignment=Alignment(vertical="top",wrap_text=True)
xlsx=OUT/"NOVEMBER_2026_THEME_QUALITY_REVIEW_V2_1.xlsx";wb.save(xlsx);check=load_workbook(xlsx,read_only=False);assert len(check.sheetnames)==7;check.close()
print(json.dumps({"topics":len(audits),"overlaps":len(overlaps),"triage_unique":len(triage),"pending":len(pending),"other":len(other),"xlsx":str(xlsx)},ensure_ascii=False));c.close()
