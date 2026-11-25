from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook,load_workbook
from openpyxl.styles import Alignment,Font,PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table,TableStyleInfo


ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"work"/"v13_workbook_data.json";OUTPUT=ROOT/"docs"/"NOVEMBER_2026_FUNDING_RADAR_QUALITY_AUDIT_V1_3.xlsx"


def main()->None:
    payload=json.loads(DATA.read_text(encoding="utf-8"));workbook=Workbook();workbook.remove(workbook.active)
    for number,(name,matrix) in enumerate(payload["sheets"].items(),1):
        sheet=workbook.create_sheet(name[:31]);columns=len(matrix[0])
        sheet.merge_cells(start_row=1,start_column=1,end_row=1,end_column=columns);cell=sheet.cell(1,1,payload["title"]);cell.fill=PatternFill("solid",fgColor="145A5A");cell.font=Font(color="FFFFFF",bold=True,size=15);cell.alignment=Alignment(vertical="center");sheet.row_dimensions[1].height=26
        sheet.merge_cells(start_row=2,start_column=1,end_row=2,end_column=columns);note=sheet.cell(2,1,"审计截止：2026-11-25；原始值不覆盖，标准化值和字段核验独立保存；新增数据不进入正式事件或公开Release。");note.fill=PatternFill("solid",fgColor="DDEDEC");note.font=Font(color="334155",italic=True)
        for ri,row in enumerate(matrix,4):
            for ci,value in enumerate(row,1):
                if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
                target=sheet.cell(ri,ci,value);target.alignment=Alignment(vertical="top",wrap_text=True)
                if ri==4:target.fill=PatternFill("solid",fgColor="B7502A");target.font=Font(color="FFFFFF",bold=True)
        last_row=len(matrix)+3;last_col=get_column_letter(columns);table=Table(displayName=f"V13Table{number}",ref=f"A4:{last_col}{last_row}");table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True);sheet.add_table(table);sheet.freeze_panes="A5";sheet.auto_filter.ref=f"A4:{last_col}{last_row}"
        for ci,header in enumerate(matrix[0],1):
            text=str(header);width=18
            if "url" in text.lower() or "URL" in text:width=44
            elif any(word in text for word in ("issue","evidence","notes","问题","依据","核验","业务","产品")):width=34
            elif "id" in text.lower():width=23
            sheet.column_dimensions[get_column_letter(ci)].width=width
            if "url" in text.lower():
                for ri in range(5,last_row+1):
                    value=sheet.cell(ri,ci)
                    if isinstance(value.value,str) and value.value.startswith("http"):value.hyperlink=value.value;value.style="Hyperlink"
    workbook.save(OUTPUT);check=load_workbook(OUTPUT,read_only=True,data_only=False);result={s:check[s].max_row-4 for s in check.sheetnames};assert len(result)==7 and result["101条候选审计"]==101 and result["字段级核验"]==707;check.close()
    print(json.dumps({"path":str(OUTPUT),"sheets":result,"bytes":OUTPUT.stat().st_size},ensure_ascii=False))


if __name__=="__main__":main()
