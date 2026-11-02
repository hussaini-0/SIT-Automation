import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = path.resolve(import.meta.dirname, "../..");
const source = path.join(root, "testcases", "sit_testcases_nbp.xlsx");
const destination = path.join(import.meta.dirname, "sit_testcases_nbp.xlsx");
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const sheet = workbook.worksheets.getItem("SIT");
const rows = sheet.getRange("A1:L481").values;
const positiveIds = new Set([
  "TC002", "TC004", "TC008", "TC009",
  "TC027", "TC028", "TC029", "TC031", "TC032",
  "TC055", "TC056", "TC063", "TC078", "TC079", "TC094", "TC231",
  "TC435", "TC436", "TC437", "TC438", "TC439", "TC440",
]);
const descriptionUpdates = new Map([
  ["TC003", "Payment - receiver rejected by counterparty"],
  ["TC005", "Payment - receiver timeout"],
  ["TC055", "Payment - sender_name 41 chars (within NBP max 140)"],
  ["TC056", "Payment - sender_name with special characters (allowed by NBP Swagger)"],
  ["TC063", "Payment - receiver_name 41 chars (within NBP max 140)"],
  ["TC078", "Payment - transaction_date omitted (optional in NBP Swagger)"],
  ["TC079", "Payment - transaction_date empty (allowed in NBP Swagger)"],
  ["TC094", "Payment - extra field accepted (NBP Swagger does not forbid it)"],
  ["TC231", "GetDefaultAccount - amount with more than two decimals (allowed by NBP Swagger)"],
]);
const negativeBusinessCases = new Set(["TC003", "TC005"]);
const prematureResponseCases = new Set(["TC047", "TC048", "TC052", "TC069", "TC090", "TC162", "TC170", "TC230"]);
const changed = [];

for (let index = 1; index < rows.length; index += 1) {
  const tcId = String(rows[index][0] ?? "");
  if (!positiveIds.has(tcId) && !negativeBusinessCases.has(tcId) && !prematureResponseCases.has(tcId)) continue;
  const currentType = String(rows[index][10] ?? "").toLowerCase();
  if (currentType !== "negative" && currentType !== "positive") {
    throw new Error(`${tcId} has unexpected test type ${currentType}`);
  }
  if (descriptionUpdates.has(tcId)) {
    sheet.getRangeByIndexes(index, 1, 1, 1).values = [[descriptionUpdates.get(tcId)]];
  }
  const isPremature = prematureResponseCases.has(tcId);
  sheet.getRangeByIndexes(index, 5, 1, 1).values = [[isPremature ? "Response ended prematurely" : positiveIds.has(tcId) ? "00" : "99"]];
  sheet.getRangeByIndexes(index, 6, 1, 1).values = [[isPremature ? "response" : "json_field"]];
  sheet.getRangeByIndexes(index, 9, 1, 1).values = [[isPremature ? null : '{"field":"response.response_code"}']];
  sheet.getRangeByIndexes(index, 10, 1, 1).values = [[positiveIds.has(tcId) ? "positive" : "negative"]];
  changed.push(tcId);
}

if (changed.length !== positiveIds.size + negativeBusinessCases.size + prematureResponseCases.size) {
  throw new Error(`Expected ${positiveIds.size + negativeBusinessCases.size + prematureResponseCases.size} cases, found ${changed.length}`);
}

workbook.recalculate();
const preview = await workbook.render({ sheetName: "SIT", range: "A1:L12", scale: 1 });
await fs.writeFile(path.join(import.meta.dirname, "nbp_cases_preview.png"), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(destination);
console.log(`Updated ${changed.join(", ")} in ${destination}`);
