import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/TalalHussain/Downloads/Report_p2m_p2p.xlsx";
const outputDir = path.resolve(import.meta.dirname);
const outputPath = path.join(outputDir, "Report_p2m_p2p.xlsx");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);

sheet.name = "Report";
sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;
sheet.tabColor = "#1F4E78";

workbook.recalculate();
const preview = await workbook.render({ sheetName: "Report", range: "A1:L18", scale: 1 });
await fs.writeFile(path.join(outputDir, "report_preview.png"), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(outputPath);
