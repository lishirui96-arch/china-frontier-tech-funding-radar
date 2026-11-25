from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "work" / "november_workbook_data.json"
OUTPUT = ROOT / "docs" / "NOVEMBER_2026_TECH_FINANCING_MA_SAMPLE_LIBRARY_V1_1.xlsx"


def main() -> None:
    payload = json.loads(DATA.read_text(encoding="utf-8"))
    workbook = Workbook()
    workbook.remove(workbook.active)
    for sheet_number, (name, matrix) in enumerate(payload["sheets"].items(), 1):
        sheet = workbook.create_sheet(name)
        columns = len(matrix[0])
        sheet.merge_cells(start_row=1,start_column=1,end_row=1,end_column=columns)
        sheet.cell(1,1,payload["title"])
        sheet.cell(1,1).fill = PatternFill("solid",fgColor="116466")
        sheet.cell(1,1).font = Font(color="FFFFFF",bold=True,size=16)
        sheet.cell(1,1).alignment = Alignment(vertical="center")
        sheet.row_dimensions[1].height = 26
        sheet.merge_cells(start_row=2,start_column=1,end_row=2,end_column=columns)
        sheet.cell(2,1,f"数据截止：{payload['cutoff']}；11月尚未结束，当前为月内增量样本，不代表全市场。")
        sheet.cell(2,1).fill = PatternFill("solid",fgColor="DDEDEC")
        sheet.cell(2,1).font = Font(color="334155",italic=True)
        for row_index,row in enumerate(matrix,start=4):
            for col_index,value in enumerate(row,start=1):
                cell = sheet.cell(row_index,col_index,value)
                cell.alignment = Alignment(vertical="top",wrap_text=True)
                if row_index == 4:
                    cell.fill = PatternFill("solid",fgColor="C65D32")
                    cell.font = Font(color="FFFFFF",bold=True)
        last_row = len(matrix)+3
        last_col = get_column_letter(columns)
        table = Table(displayName=f"SampleTable{sheet_number}",ref=f"A4:{last_col}{last_row}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2",showFirstColumn=False,showLastColumn=False,showRowStripes=True,showColumnStripes=False)
        sheet.add_table(table)
        sheet.freeze_panes = "A5"
        sheet.auto_filter.ref = f"A4:{last_col}{last_row}"
        for col_index,header in enumerate(matrix[0],start=1):
            width = 16
            if "URL" in header or "来源链接" in header: width = 46
            elif any(term in header for term in ("说明","技术","依据","边界","问题","用途","投资方","涉及企业","新闻标题","交易依据")): width = 32
            elif "_id" in header or "ID" in header: width = 21
            sheet.column_dimensions[get_column_letter(col_index)].width = width
            if "URL" in header or "来源链接" in header:
                for row_index in range(5,last_row+1):
                    cell = sheet.cell(row_index,col_index)
                    if isinstance(cell.value,str) and cell.value.startswith("http") and "|" not in cell.value:
                        cell.hyperlink = cell.value; cell.style = "Hyperlink"
        if name == "月度统计":
            for row_index in range(5,last_row+1):
                sheet.cell(row_index,7).number_format = '#,##0'
                sheet.cell(row_index,8).number_format = '0.0%'
    workbook.save(OUTPUT)
    check = load_workbook(OUTPUT,read_only=False,data_only=False)
    result = {sheet.title: sheet.max_row-4 for sheet in check.worksheets}
    assert list(result) == list(payload["sheets"])
    assert result["融资事件明细"] >= 22 and result["并购事件明细"] == 6
    check.close()
    print(json.dumps({"path":str(OUTPUT),"sheets":result,"bytes":OUTPUT.stat().st_size},ensure_ascii=False))


if __name__ == "__main__": main()
