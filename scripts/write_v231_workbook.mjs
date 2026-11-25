import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const datasets = JSON.parse(await fs.readFile(path.join(root, "work", "v231_workbook_data.json"), "utf8"));
const workbook = Workbook.create();
const names = Object.keys(datasets);
for (const name of names) {
  const sheet = workbook.worksheets.add(name.slice(0, 31));
  const records = datasets[name];
  const headers = records.length ? Object.keys(records[0]) : ["无数据"];
  const values = [headers, ...records.map((row) => headers.map((key) => {
    const value = row[key];
    return value && typeof value === "object" ? JSON.stringify(value) : (value ?? "");
  }))];
  const range = sheet.getRangeByIndexes(0, 0, values.length, headers.length);
  range.values = values;
  range.format.font = { name: "Arial", size: 10, color: "#1F2937" };
  range.format.verticalAlignment = "top";
  range.format.wrapText = true;
  const header = sheet.getRangeByIndexes(0, 0, 1, headers.length);
  header.format.fill = "#1F4E78";
  header.format.font = { name: "Arial", size: 10, bold: true, color: "#FFFFFF" };
  header.format.horizontalAlignment = "center";
  range.format.autofitColumns();
  for (let col = 0; col < headers.length; col++) {
    const column = sheet.getRangeByIndexes(0, col, values.length, 1);
    if (column.format.columnWidth > 32) column.format.columnWidth = 32;
    if (column.format.columnWidth < 10) column.format.columnWidth = 10;
    if (headers[col].endsWith("_at")) column.format.numberFormat = "yyyy-mm-dd hh:mm";
  }
  sheet.freezePanes.freezeRows(1);
  sheet.showGridlines = false;
}
workbook.recalculate();
const outputDir = path.join(root, "docs");
await fs.mkdir(outputDir, { recursive: true });
const outputPath = path.join(outputDir, "NOVEMBER_2026_TOPIC_ADMISSION_REVIEW_V2_3_1.xlsx");
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const preview = await workbook.render({ sheetName: "修订候选清单", range: "A1:P15", scale: 1, format: "png" });
await fs.writeFile(path.join(root, "work", "v231_workbook_preview.png"), new Uint8Array(await preview.arrayBuffer()));
const inspection = await workbook.inspect({ kind: "table", range: "修订候选清单!A1:P15", include: "values,formulas", tableMaxRows: 15, tableMaxCols: 16 });
console.log(JSON.stringify({ outputPath, sheets: names.length, inspection: inspection.ndjson.slice(0, 2000) }));
