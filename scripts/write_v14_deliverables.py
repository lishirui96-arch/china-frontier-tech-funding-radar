from __future__ import annotations
import csv,json,sqlite3
from collections import Counter
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table,TableStyleInfo
from funding_radar.db import database_path

ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/"docs"

def rows(con,sql): return [dict(x) for x in con.execute(sql).fetchall()]
def write_csv(path,data):
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]) if data else ["empty"]); w.writeheader(); w.writerows(data)
def matrix(data): return [list(data[0]),*[list(r.values()) for r in data]] if data else [["无记录"]]

def main():
    con=sqlite3.connect(database_path()); con.row_factory=sqlite3.Row
    events=rows(con,"""select u.*,a.original_company_name,a.source_title,a.source_url,a.evidence_grade,a.quality_issues_json,
      r.adjudication_type,r.proposed_rounds_json,r.basis round_basis,r.handling_recommendation,r.review_status round_review_status
      from v14_event_units u join v13_candidate_quality_audits a using(audit_id) left join v14_round_adjudications r using(audit_id)
      order by u.disclosure_date desc,u.adjudicated_company_name""")
    companies=rows(con,"select * from v14_company_revisions order by confirmed_display_name")
    duplicates=rows(con,"""select d.*,l.normalized_company_name left_company,l.source_url left_url,r.normalized_company_name right_company,r.source_url right_url
      from v14_duplicate_decisions d join v13_candidate_relations x using(relation_id)
      join v13_candidate_quality_audits l on l.audit_id=x.left_audit_id join v13_candidate_quality_audits r on r.audit_id=x.right_audit_id""")
    acquisitions=rows(con,"select * from v13_acquisition_verifications order by first_announcement_date desc")
    round_rows=rows(con,"""select r.*,a.normalized_company_name,a.normalized_disclosure_date,a.source_title,a.source_url
      from v14_round_adjudications r join v13_candidate_quality_audits a using(audit_id) order by a.normalized_company_name""")
    actions=rows(con,"select * from v14_review_actions order by occurred_at desc")
    summary=[{"指标":"候选记录","数量":len(events)},{"指标":"可用于统计准备（A类）","数量":sum(x['sample_eligibility_status']=='A_statistical' for x in events)},{"指标":"待核验（B类）","数量":sum(x['sample_eligibility_status']=='B_pending' for x in events)},{"指标":"排除/重复来源（C类）","数量":sum(x['sample_eligibility_status']=='C_excluded' for x in events)},{"指标":"建议拆分","数量":sum(x['event_structure_status']=='split_recommended' for x in events)},{"指标":"重复来源合并","数量":len(duplicates)},{"指标":"企业名称修订记录","数量":len(companies)},{"指标":"并购候选","数量":len(acquisitions)}]
    write_csv(DOCS/"NOVEMBER_2026_V1_4_EVENT_ADJUDICATION.csv",events)
    write_csv(DOCS/"NOVEMBER_2026_V1_4_COMPANY_REVISIONS.csv",companies)
    write_csv(DOCS/"NOVEMBER_2026_V1_4_DUPLICATE_DECISIONS.csv",duplicates)
    write_csv(DOCS/"NOVEMBER_2026_V1_4_ACQUISITION_VERIFICATIONS.csv",acquisitions)
    write_csv(DOCS/"NOVEMBER_2026_V1_4_REVIEW_QUEUE.csv",events)
    dist=Counter(x['adjudicated_round'] for x in events if x['sample_eligibility_status']=='A_statistical')
    report=f"""# 融资雷达 V1.4 数据质量审计报告

审计截止：2026-11-25。V1.4只建立候选裁决层和人工审核准备，不提升正式事件，不创建公开Release。

## 结果

- 候选记录：{len(events)}
- 暂定独立事件单元：{len({x['canonical_event_id'] for x in events})}
- 属于2026年11月披露：{sum('2026-11-01'<=x['disclosure_date']<='2026-11-25' for x in events)}
- A类可用于统计准备：{sum(x['sample_eligibility_status']=='A_statistical' for x in events)}
- B类待核验：{sum(x['sample_eligibility_status']=='B_pending' for x in events)}
- C类排除或重复来源：{sum(x['sample_eligibility_status']=='C_excluded' for x in events)}
- 建议拆分：{sum(x['event_structure_status']=='split_recommended' for x in events)}
- 建议合并来源：{len(duplicates)}
- 企业名称修订记录：{len(companies)}（法定主体未知时保持为空）
- 并购候选：{len(acquisitions)}

## A类轮次分布

{chr(10).join(f'- {k}: {v}' for k,v in sorted(dist.items()))}

## 裁决边界

- 同文明确并列两轮的记录标记为建议拆分，但在人工确认各轮日期、金额和投资方前仍属于B类。
- B/B+等媒体冲突保持单条待审，不自动拆分或合并。
- 四组确认重复关系以主事件承载，附加报道保留为来源，重复记录属于C类且不重复计数。
- A/B/C为样本资格，与S/A/B/C/D证据等级相互独立。
- 披露日期不代表实际交割日期；并购公告不等于完成交割。
"""
    (DOCS/"NOVEMBER_2026_V1_4_DATA_QUALITY_REPORT.md").write_text(report,encoding="utf-8")
    sheets={"质量摘要":summary,"融资事件裁决":events,"轮次冲突裁决":round_rows,"企业实体修订":companies,"重复事件处理":duplicates,"并购核验":acquisitions,"人工审核队列":events}
    wb=Workbook(); wb.remove(wb.active)
    for i,(name,data) in enumerate(sheets.items(),1):
        ws=wb.create_sheet(name); mat=matrix(data); cols=len(mat[0]); ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=cols); ws.cell(1,1,"融资雷达 V1.4 融资事件拆分、冲突裁决与人工审核准备"); ws.cell(1,1).font=Font(color="FFFFFF",bold=True,size=15); ws.cell(1,1).fill=PatternFill("solid",fgColor="145A5A"); ws.merge_cells(start_row=2,start_column=1,end_row=2,end_column=cols); ws.cell(2,1,"A/B/C为样本资格，不是证据等级；自动预裁决须经人工审核，不进入正式事件或公开Release。"); ws.cell(2,1).fill=PatternFill("solid",fgColor="DDEDEC")
        for rr,row in enumerate(mat,4):
            for cc,val in enumerate(row,1):
                if isinstance(val,(dict,list)): val=json.dumps(val,ensure_ascii=False)
                c=ws.cell(rr,cc,val); c.alignment=Alignment(vertical="top",wrap_text=True)
                if rr==4: c.font=Font(color="FFFFFF",bold=True); c.fill=PatternFill("solid",fgColor="B7502A")
        last=len(mat)+3; end=get_column_letter(cols); t=Table(displayName=f"V14Table{i}",ref=f"A4:{end}{last}"); t.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True); ws.add_table(t); ws.freeze_panes="A5"
        for cc,h in enumerate(mat[0],1): ws.column_dimensions[get_column_letter(cc)].width=42 if "url" in str(h).lower() else (30 if any(k in str(h) for k in ("reason","basis","依据","理由","建议")) else 20)
    out=DOCS/"NOVEMBER_2026_FUNDING_RADAR_EVENT_ADJUDICATION_V1_4.xlsx"; wb.save(out); check=load_workbook(out,read_only=True); assert len(check.sheetnames)==7; check.close()
    print(json.dumps({"xlsx":str(out),"sheets":7,"events":len(events),"companies":len(companies),"duplicates":len(duplicates),"acquisitions":len(acquisitions)},ensure_ascii=False))

if __name__=="__main__": main()
