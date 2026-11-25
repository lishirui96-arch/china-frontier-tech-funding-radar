from __future__ import annotations
import csv,json,sqlite3
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table,TableStyleInfo
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/"docs"
def rows(db,sql): return [dict(x) for x in db.execute(sql).fetchall()]
def csvout(name,data):
    with (DOCS/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]) if data else ["status"]); w.writeheader(); w.writerows(data or [{"status":"尚无人工审核记录"}])
def mat(data): return [list(data[0]),*[list(x.values()) for x in data]] if data else [["状态"],["尚无人工确认记录"]]

def main():
    db=sqlite3.connect(database_path()); db.row_factory=sqlite3.Row
    queue_sql="""select q.*,u.disclosure_date,u.amount_original,a.original_company_name,a.source_title,a.source_url,a.evidence_grade,
      e.primary_business,e.core_products,e.primary_category original_primary_category,e.secondary_track original_secondary_track
      from v15_funding_review_queue q join v14_event_units u using(event_unit_id)
      join v13_candidate_quality_audits a using(audit_id) join v13_company_entities e using(company_id)
      order by q.batch_number,u.disclosure_date desc"""
    allq=rows(db,queue_sql); a=[x for x in allq if x["queue_class"]=="A"]; b=[x for x in allq if x["queue_class"]=="B"]
    ma=rows(db,"select q.*,v.* from v15_acquisition_review_queue q join v13_acquisition_verifications v using(acquisition_key) order by first_announcement_date desc")
    confirmed=rows(db,"select * from v15_confirmed_funding_events where is_active=1 order by disclosure_date desc")
    tech=rows(db,"select * from v15_technology_analysis order by primary_category,secondary_track,company_name")
    actions=rows(db,"""select 'funding' scope,action_id,review_item_id,decision,actor,reason,occurred_at from v15_funding_review_actions
      union all select 'acquisition',action_id,review_item_id,decision,actor,reason,occurred_at from v15_acquisition_review_actions order by occurred_at desc""")
    summary=[{"指标":"A类审核队列","数量":len(a)},{"指标":"B类专项队列","数量":len(b)},{"指标":"并购审核队列","数量":len(ma)},{"指标":"人工确认正式融资事件","数量":len(confirmed)},{"指标":"暂缓","数量":sum(x['review_status']=='held' for x in allq)},{"指标":"排除","数量":sum(x['review_status']=='excluded' for x in allq)},{"指标":"技术分析准备记录","数量":len(tech)},{"指标":"人工审核操作","数量":len(actions)}]
    csvout("NOVEMBER_2026_V1_5_A_REVIEW_QUEUE.csv",a); csvout("NOVEMBER_2026_V1_5_B_REVIEW_QUEUE.csv",b); csvout("NOVEMBER_2026_V1_5_ACQUISITION_REVIEW_QUEUE.csv",ma); csvout("NOVEMBER_2026_V1_5_CONFIRMED_FUNDING_EVENTS.csv",confirmed); csvout("NOVEMBER_2026_V1_5_TECHNOLOGY_ANALYSIS.csv",tech); csvout("NOVEMBER_2026_V1_5_REVIEW_ACTIONS.csv",actions)
    report=f"""# 融资雷达 V1.5 人工审核准备报告

审计截止：2026-11-25。本版本建立人工审核基础设施，不代替用户作出决定，不创建公开Release。

- A类审核队列：{len(a)}条，分4批（20、20、20、19）
- B类专项审核队列：{len(b)}条
- 并购审核队列：{len(ma)}条
- 已人工审核：{sum(x['review_status']!='pending' for x in allq)}条
- 正式纳入：{len(confirmed)}条
- 暂缓：{sum(x['review_status']=='held' for x in allq)}条
- 排除：{sum(x['review_status']=='excluded' for x in allq)}条
- 尚未解决：{sum(x['review_status']=='pending' for x in allq)}条融资候选、{sum(x['review_status']=='pending' for x in ma)}条并购候选

正式统计和技术分析表只读取人工确认纳入的事件。未披露金额保持空值，不填0。当前没有代替用户执行任何审核决定。
"""
    (DOCS/"NOVEMBER_2026_V1_5_HUMAN_REVIEW_PREPARATION_REPORT.md").write_text(report,encoding="utf-8")
    sheets={"审核概览":summary,"A类79条审核队列":a,"B类18条专项审核":b,"并购8条审核队列":ma,"正式融资事件":confirmed,"技术主题分析准备":tech,"人工审核操作记录":actions}
    wb=Workbook(); wb.remove(wb.active)
    for i,(name,data) in enumerate(sheets.items(),1):
        ws=wb.create_sheet(name); matrix=mat(data); cols=len(matrix[0]); ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=cols); ws.cell(1,1,"融资雷达 V1.5 人工审核与月度样本冻结准备"); ws.cell(1,1).font=Font(color="FFFFFF",bold=True,size=15); ws.cell(1,1).fill=PatternFill("solid",fgColor="145A5A"); ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=cols); ws.cell(2,1,"默认不执行审核决定；正式样本、统计和技术主题准备仅由人工确认动作生成。"); ws.cell(2,1).fill=PatternFill("solid",fgColor="DDEDEC")
        for rr,row in enumerate(matrix,4):
            for cc,val in enumerate(row,1):
                if isinstance(val,(dict,list)): val=json.dumps(val,ensure_ascii=False)
                c=ws.cell(rr,cc,val); c.alignment=Alignment(vertical="top",wrap_text=True)
                if rr==4: c.font=Font(color="FFFFFF",bold=True); c.fill=PatternFill("solid",fgColor="B7502A")
        last=len(matrix)+3; end=get_column_letter(cols); table=Table(displayName=f"V15Table{i}",ref=f"A4:{end}{last}"); table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True); ws.add_table(table); ws.freeze_panes="A5"
        for cc,h in enumerate(matrix[0],1): ws.column_dimensions[get_column_letter(cc)].width=44 if "url" in str(h).lower() else (30 if any(k in str(h) for k in ("snapshot","notes","reason","业务","产品")) else 20)
    out=DOCS/"NOVEMBER_2026_FUNDING_RADAR_HUMAN_REVIEW_V1_5.xlsx"; wb.save(out); check=load_workbook(out,read_only=True); assert len(check.sheetnames)==7; check.close(); print(json.dumps({"xlsx":str(out),"A":len(a),"B":len(b),"MA":len(ma),"confirmed":len(confirmed),"actions":len(actions)},ensure_ascii=False))
if __name__=="__main__": main()
