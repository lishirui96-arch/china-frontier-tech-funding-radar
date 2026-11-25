from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"work"/"v12_workbook_data.json"
OUTPUT=ROOT/"docs"/"NOVEMBER_2026_TECH_FINANCING_MA_SAMPLE_LIBRARY_V1_2.xlsx"


def main()->None:
    payload=json.loads(DATA.read_text(encoding="utf-8"))
    workbook=Workbook();workbook.remove(workbook.active)
    for number,(name,matrix) in enumerate(payload["sheets"].items(),1):
        sheet=workbook.create_sheet(name[:31]);columns=len(matrix[0])
        sheet.merge_cells(start_row=1,start_column=1,end_row=1,end_column=columns)
        title=sheet.cell(1,1,payload["title"]);title.fill=PatternFill("solid",fgColor="145A5A");title.font=Font(color="FFFFFF",bold=True,size=15);title.alignment=Alignment(vertical="center")
        sheet.row_dimensions[1].height=26
        sheet.merge_cells(start_row=2,start_column=1,end_row=2,end_column=columns)
        note=sheet.cell(2,1,f"披露窗口：2026-11-01至{payload['cutoff']}；新增数据均为待审核候选，不进入公开Release。")
        note.fill=PatternFill("solid",fgColor="DDEDEC");note.font=Font(color="334155",italic=True)
        for row_index,row in enumerate(matrix,4):
            for col_index,value in enumerate(row,1):
                if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
                cell=sheet.cell(row_index,col_index,value);cell.alignment=Alignment(vertical="top",wrap_text=True)
                if row_index==4:cell.fill=PatternFill("solid",fgColor="B7502A");cell.font=Font(color="FFFFFF",bold=True)
        last_row=len(matrix)+3;last_col=get_column_letter(columns)
        table=Table(displayName=f"V12Table{number}",ref=f"A4:{last_col}{last_row}");table.tableStyleInfo=TableStyleInfo(name="TableStyleMedium2",showRowStripes=True)
        sheet.add_table(table);sheet.freeze_panes="A5";sheet.auto_filter.ref=f"A4:{last_col}{last_row}"
        for col_index,header in enumerate(matrix[0],1):
            header_text=str(header);width=18
            if "url" in header_text.lower() or "URL" in header_text:width=45
            elif any(word in header_text for word in ("title","标题","notes","问题","核验","依据","投资方","raw_json")):width=34
            elif "id" in header_text.lower():width=23
            sheet.column_dimensions[get_column_letter(col_index)].width=width
            if "url" in header_text.lower() or "URL" in header_text:
                for row_index in range(5,last_row+1):
                    cell=sheet.cell(row_index,col_index)
                    if isinstance(cell.value,str) and cell.value.startswith("http"):
                        cell.hyperlink=cell.value;cell.style="Hyperlink"
    workbook.save(OUTPUT)
    check=load_workbook(OUTPUT,read_only=True,data_only=False)
    result={sheet.title:sheet.max_row-4 for sheet in check.worksheets}
    assert len(result)==7 and result["SpaceDaily 95条"]==95 and result["V1.1候选核验"]==72
    check.close()
    print(json.dumps({"path":str(OUTPUT),"sheets":result,"bytes":OUTPUT.stat().st_size},ensure_ascii=False))


if __name__=="__main__":main()
