import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "..");
const data = JSON.parse(await fs.readFile(path.join(root, "work", "v30_workbook_data.json"), "utf8"));
const workbook = Workbook.create();
for (const [name, records] of Object.entries(data)) {
  const sheet = workbook.worksheets.add(name.slice(0,31));
  const headers = records.length ? Object.keys(records[0]) : ["无数据"];
  const values = [headers, ...records.map(row => headers.map(key => {
    const value = row[key]; return value && typeof value === "object" ? JSON.stringify(value) : (value ?? "");
  }))];
  const range = sheet.getRangeByIndexes(0,0,values.length,headers.length);
  range.values = values; range.format.font = {name:"Arial",size:10,color:"#1F2937"};
  range.format.verticalAlignment="top"; range.format.wrapText=true;
  const header=sheet.getRangeByIndexes(0,0,1,headers.length); header.format.fill="#164E63";
  header.format.font={name:"Arial",size:10,bold:true,color:"#FFFFFF"}; header.format.horizontalAlignment="center";
  range.format.autofitColumns();
  for (let col=0;col<headers.length;col++) { const column=sheet.getRangeByIndexes(0,col,values.length,1); if(column.format.columnWidth>30)column.format.columnWidth=30;if(column.format.columnWidth<10)column.format.columnWidth=10; }
  sheet.freezePanes.freezeRows(1); sheet.showGridlines=false;
}
workbook.recalculate();
const outputPath=path.join(root,"docs","NOVEMBER_2026_FUNDING_RADAR_V3_0.xlsx");
const output=await SpreadsheetFile.exportXlsx(workbook); await output.save(outputPath);
const preview=await workbook.render({sheetName:"三级分类总表",range:"A1:J35",scale:1,format:"png"});
await fs.writeFile(path.join(root,"work","v30_workbook_preview.png"),new Uint8Array(await preview.arrayBuffer()));
const inspection=await workbook.inspect({kind:"table",range:"97条迁移对照!A1:T12",include:"values,formulas",tableMaxRows:12,tableMaxCols:20});
console.log(JSON.stringify({outputPath,sheets:Object.keys(data).length,inspection:inspection.ndjson.slice(0,1200)}));
