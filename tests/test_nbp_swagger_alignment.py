import json
import unittest
from pathlib import Path

import yaml
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "SIT": ("cas", "9091"),
    "MERCHANT_CAS": ("merchant_cas", "9093"),
    "ACQUIRING": ("acquiring", "9096"),
}
EXCLUDED = {
    ("/api/v1/paysyslabs/customers/registercaa", "POST"),
    # NBP's current 9093 sender-side suite does not execute receiver RTP
    # payment routes. Those routes are configured per receiving bank later.
    ("/api/v1/paysyslabs/merchant/payment/direct/SQRC", "POST"),
    ("/api/v1/paysyslabs/merchant/payment/direct/RTPN", "POST"),
    ("/api/v1/paysyslabs/merchant/payment/direct/RTPL", "POST"),
    ("/api/v1/paysyslabs/merchant/payment/RTPN", "POST"),
    ("/api/v1/paysyslabs/merchant/payment/RTPL", "POST"),
}


class NbpSwaggerAlignmentTests(unittest.TestCase):
    def test_every_in_scope_operation_has_an_nbp_case(self):
        base = yaml.safe_load((ROOT / "config" / "apis.yaml").read_text(encoding="utf-8"))["services"]
        extra = yaml.safe_load((ROOT / "config" / "apis_nbp.yaml").read_text(encoding="utf-8"))["services"]
        workbook = load_workbook(ROOT / "testcases" / "sit_testcases_nbp.xlsx", read_only=True, data_only=True)

        for sheet, (service, port) in SPECS.items():
            with self.subTest(sheet=sheet):
                spec = json.loads((ROOT / "specs" / "nbp" / f"{port}.openapi.json").read_text(encoding="utf-8"))
                expected = {
                    (path, method.upper())
                    for path, methods in spec["paths"].items()
                    for method in methods
                    if method.lower() in {"get", "post", "put", "patch", "delete"}
                } - EXCLUDED
                definitions = {
                    **base[service]["apis"],
                    **extra.get(service, {}).get("apis", {}),
                }
                rows = workbook[sheet].iter_rows(values_only=True)
                headers = {name: index for index, name in enumerate(next(rows)) if name}
                covered = set()
                for row in rows:
                    if not row[headers["TC_ID"]]:
                        continue
                    if str(row[headers["TC_ID"]]).startswith("NBP_SWAGGER_"):
                        self.assertEqual(row[headers["Execute (Y/N)"]], "N")
                    self.assertEqual(str(row[headers["Bank"]]).lower(), "nbp")
                    api_name = str(row[headers["API_Name"]])
                    self.assertIn(api_name, definitions)
                    request_file = str(row[headers["Request_File"]] or "")
                    self.assertTrue((ROOT / "requests" / service / request_file).is_file(), request_file)
                    definition = definitions[api_name]
                    route = ("/" + definition["endpoint"].split("?", 1)[0].lstrip("/"), definition["method"].upper())
                    if route in expected:
                        covered.add(route)
                self.assertEqual(covered, expected)


if __name__ == "__main__":
    unittest.main()
