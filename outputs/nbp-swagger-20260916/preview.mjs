import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const dir = new URL(".", import.meta.url);
const root = new URL("../../", dir);
const file = new URL("testcases/sit_testcases_nbp.xlsx", root);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file.pathname.slice(1)));
const summary = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 2000,
});
console.log(summary.ndjson);
const sample = await workbook.inspect({
  kind: "region",
  sheetId: "MERCHANT_CAS",
  range: "A1:L8",
  maxChars: 3500,
});
console.log(sample.ndjson);
const preview = await workbook.render({
  sheetName: "MERCHANT_CAS",
  range: "A1:L8",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(new URL("before_merchant.png", dir), new Uint8Array(await preview.arrayBuffer()));
