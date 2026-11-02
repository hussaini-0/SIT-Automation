import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const dir = new URL(".", import.meta.url);
const source = new URL("../../testcases/sit_testcases_nbp.xlsx", dir);
const changes = JSON.parse(await fs.readFile(new URL("workbook_changes.json", dir), "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source.pathname.slice(1)));

for (const change of changes) {
  const sheet = workbook.worksheets.getItem(change.sheet);
  sheet.getRangeByIndexes(change.row - 1, 4, 1, 1).values = [[change.request_file]];
  if (change.execute) {
    sheet.getRangeByIndexes(change.row - 1, 7, 1, 1).values = [[change.execute]];
  }
}

workbook.recalculate();
for (const address of ["E16", "E17", "E18", "H41", "E185"]) {
  const sample = await workbook.inspect({
    kind: "region",
    sheetId: "MERCHANT_CAS",
    range: address,
    maxChars: 500,
  });
  console.log(sample.ndjson);
}
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 30 },
  maxChars: 1500,
});
console.log(errors.ndjson);
const preview = await workbook.render({
  sheetName: "MERCHANT_CAS",
  range: "A14:L18",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(new URL("after_merchant.png", dir), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(new URL("sit_testcases_nbp.xlsx", dir).pathname.slice(1));
