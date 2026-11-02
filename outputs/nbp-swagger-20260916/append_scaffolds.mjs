import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const dir = new URL(".", import.meta.url);
const source = new URL("../../testcases/sit_testcases_nbp.xlsx", dir);
const additions = JSON.parse(await fs.readFile(new URL("workbook_additions.json", dir), "utf8"));
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source.pathname.slice(1)));
const nextRow = { SIT: 455, MERCHANT_CAS: 211 };

for (const item of additions) {
  const sheet = workbook.worksheets.getItem(item.sheet);
  const values = [
    item.tc_id,
    item.description,
    item.bank,
    item.api_name,
    item.request_file,
    item.expected_result,
    item.validation_type,
    item.execute,
    "",
    "",
    item.test_type,
    item.trx_type,
  ];
  sheet.getRangeByIndexes(nextRow[item.sheet], 0, 1, values.length).values = [values];
  nextRow[item.sheet] += 1;
}

workbook.recalculate();
const preview = await workbook.render({
  sheetName: "SIT",
  range: "A454:L458",
  scale: 1.5,
  format: "png",
});
await fs.writeFile(new URL("scaffolds.png", dir), new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(new URL("sit_testcases_nbp.xlsx", dir).pathname.slice(1));
console.log(JSON.stringify({ added: additions.length, nextRow }));
