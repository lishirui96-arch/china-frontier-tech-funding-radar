from __future__ import annotations
import csv,json,sqlite3,itertools
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.utils import get_column_letter
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/"docs";OUT.mkdir(exist_ok=True)
c=sqlite3.connect(database_path());c.row_factory=sqlite3.Row
def rows(sql,args=()): return [dict(x) for x in c.execute(sql,args)]
profiles=rows("select * from v211_profile_reviews order by suggested_name")
dups=rows("select d.*,l.company_name left_name,r.company_name right_name from v211_entity_duplicate_checks d join v2_company_profiles l on l.profile_id=d.left_profile_id join v2_company_profiles r on r.profile_id=d.right_profile_id")
triage=rows("""select x.*,p.company_name,r.quality_status,r.suggested_business,r.suggested_products,r.suggested_technologies from v21_profile_triage x join v2_company_profiles p using(profile_id) join v211_profile_reviews r using(profile_id) order by p.company_name""")
links=rows("""select x.*,p.company_name,t.candidate_name from v211_product_technology_topic_links x join v2_company_profiles p using(profile_id) left join v2_candidate_topics t using(topic_id) order by p.company_name,t.candidate_name""")
shared=rows("select s.*,p.company_name from v211_shared_company_reviews s join v2_company_profiles p using(profile_id) order by p.company_name")
splits=rows("""select s.*,t.candidate_name source_topic,group_concat(p.company_name) companies from v211_split_proposals s join v2_candidate_topics t on t.topic_id=s.source_topic_id left join v211_split_members m using(proposal_id) left join v2_company_profiles p using(profile_id) group by s.proposal_id order by source_topic,subtopic_name""")
issues=[]
for p in profiles:
    for issue in json.loads(p["issues_json"]): issues.append({"企业":p["suggested_name"],"质量状态":p["quality_status"],"字段问题":issue,"处理建议":p["reason"]})
datasets={"123家画像清洗":profiles,"实体重复检查":dups,"53家待处理复核":triage,"产品技术主题关联":links,"共享企业复核":shared,"8主题拆分方案":splits,"字段问题清单":issues}
for name,data in datasets.items():
    with (OUT/f"V211_{name}.csv").open("w",encoding="utf-8-sig",newline="") as f:
        if data:w=csv.DictWriter(f,fieldnames=data[0]);w.writeheader();w.writerows(data)

quality={r["quality_status"]:r["n"] for r in c.execute("select quality_status,count(*) n from v211_profile_reviews group by quality_status")}
fit={r["topic_fit"]:r["n"] for r in c.execute("select topic_fit,count(*) n from v211_product_technology_topic_links group by topic_fit")}
ready=rows("""select t.candidate_name,count(*) members,sum(x.topic_fit='supported') supported
 from v2_candidate_topics t join v211_product_technology_topic_links x using(topic_id)
 group by t.topic_id having members>=2 and supported=members""")
similarity=[]
for topic in rows("select topic_id,candidate_name from v2_candidate_topics order by candidate_name"):
    sets=[]
    for item in rows("select p.keywords_json from v2_company_topic_links l join v2_company_profiles p using(profile_id) where l.topic_id=? and l.is_current=1",(topic["topic_id"],)):
        sets.append(set(json.loads(item["keywords_json"] or "[]")))
    pairs=[len(a&b)/len(a|b) for a,b in itertools.combinations(sets,2) if a|b]
    similarity.append({"topic":topic["candidate_name"],"similarity":round(sum(pairs)/len(pairs),3) if pairs else None,"missing":sum(not x for x in sets),"members":len(sets)})
report=["# V2.1.1 企业技术画像数据质量报告","","本轮仅生成画像修订与主题拆分建议，不修改V2.0/V2.1主题结构。","",f"- 画像总数：{len(profiles)}",f"- 已有具体依据：{quality.get('accurate',0)}",f"- 需要修改：{quality.get('needs_revision',0)}",f"- 缺少核心业务信息：{quality.get('missing_core_business',0)}",f"- 实体重复候选：{len(dups)}",f"- 53家待处理企业：{len(triage)}",f"- 共享主题企业：{len(shared)}",f"- 拆分候选子组：{len(splits)}","", "## 主题关联质量",""]
report += [f"- {k}：{v}" for k,v in fit.items()]
report += ["","## 关键词相似度边界检查","","相似度仅用于发现异常，不参与排名，也不通过补词人为提高。"]
report += [f"- {x['topic']}：相似度 {x['similarity'] if x['similarity'] is not None else '不可计算'}；缺关键词画像 {x['missing']}/{x['members']}" for x in similarity if x['similarity'] in (0,1) or x['missing']]
report += ["","## 当前具备定稿数据条件的主题","",*(f"- {x['candidate_name']}（{x['members']}家企业）" for x in ready),"","该清单只表示成员均有产品与技术字段依据，仍需用户决定名称和边界；其中V2.1建议拆分的主题不能直接定稿。"]
(OUT/"V211_DATA_QUALITY_REPORT.md").write_text("\n".join(report)+"\n",encoding="utf-8")
shared_md=["# V2.1.1 共享企业复核","","多主题关系必须有产品和技术依据。",""]
for x in shared: shared_md += [f"## {x['company_name']}","",f"- 结论：{x['review_conclusion']}",f"- 问题：{x['issues']}","",json.dumps(json.loads(x['topic_basis_json']),ensure_ascii=False,indent=2),""]
(OUT/"V211_SHARED_COMPANY_REVIEW.md").write_text("\n".join(shared_md),encoding="utf-8")
split_md=["# V2.1.1 八个主题拆分方案",""]
for x in splits: split_md += [f"## {x['source_topic']} → {x['subtopic_name']}","",f"- 企业：{x['companies'] or '—'}",f"- 企业/事件：{x['company_count']}/{x['event_count']}",f"- 正式/A/B：{x['formal_count']}/{x['a_count']}/{x['b_count']}",f"- 状态：{x['proposal_status']}",f"- 依据：{x['split_basis']}",""]
(OUT/"V211_SPLIT_TOPIC_PROPOSALS.md").write_text("\n".join(split_md),encoding="utf-8")
wb=Workbook();wb.remove(wb.active)
for name,data in datasets.items():
    ws=wb.create_sheet(name[:31]);heads=list(data[0]) if data else ["无数据"];ws.append(heads)
    for x in data:ws.append([x[h] if not isinstance(x[h],(dict,list)) else json.dumps(x[h],ensure_ascii=False) for h in heads])
    for cell in ws[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="1F4E78")
    ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
    for idx,col in enumerate(ws.columns,1):
        ws.column_dimensions[get_column_letter(idx)].width=min(50,max(10,max(len(str(x.value or "")) for x in col)+2))
        for cell in col:cell.alignment=Alignment(vertical="top",wrap_text=True)
xlsx=OUT/"NOVEMBER_2026_COMPANY_PROFILE_QUALITY_V2_1_1.xlsx";wb.save(xlsx);check=load_workbook(xlsx,read_only=False);assert len(check.sheetnames)==7;check.close()
print(json.dumps({"profiles":len(profiles),"quality":quality,"triage":len(triage),"shared":len(shared),"split_groups":len(splits),"ready_topics":len(ready),"xlsx":str(xlsx)},ensure_ascii=False));c.close()
