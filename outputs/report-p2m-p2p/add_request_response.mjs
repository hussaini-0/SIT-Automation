import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/TalalHussain/Downloads/Report_p2m_p2p_direct.xlsx";
const resultPath = "C:/Users/TalalHussain/GitProjects/SIT-Automation/results/results_acquiring-cas-merchant-cas_20260916_185620.json";
const outputPath = "C:/Users/TalalHussain/GitProjects/SIT-Automation/outputs/report-p2m-p2p/Report_p2m_p2p_request_response.xlsx";
const previewPath = "C:/Users/TalalHussain/GitProjects/SIT-Automation/outputs/report-p2m-p2p/report_request_response_preview.png";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getActiveWorksheet();
const rows = sheet.getUsedRange().values;
const resultDoc = JSON.parse(await fs.readFile(resultPath, "utf8"));
const byTc = new Map(resultDoc.results.map((r) => [String(r.tc_id), r]));

rows[0][10] = "Request";
rows[0][12] = "Response";
for (let i = 1; i < rows.length; i++) {
  const tcId = String(rows[i][0] ?? "");
  const result = byTc.get(tcId);
  if (result) {
    rows[i][10] = JSON.stringify(result.request_payload ?? {}, null, 2);
    rows[i][12] = JSON.stringify(result.response_body ?? {}, null, 2);
  } else {
    rows[i][10] = "";
    rows[i][12] = "";
  }
}

sheet.getUsedRange().values = rows;
sheet.getRange(`K2:K${rows.length}`).format.wrapText = true;
sheet.getRange(`M2:M${rows.length}`).format.wrapText = true;
sheet.getRange(`K:K`).format.columnWidth = 42;
sheet.getRange(`M:M`).format.columnWidth = 42;
sheet.getRange(`K1:M${rows.length}`).format.verticalAlignment = "top";
workbook.recalculate();

const preview = await workbook.render({ sheetName: sheet.name, range: "A1:N8", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewPath, rows: rows.length - 1, matched: rows.slice(1).filter((r) => r[10]).length }));
