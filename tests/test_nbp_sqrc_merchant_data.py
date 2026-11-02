import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from runner import SITRunner
from testcase_models import ServiceTestCase
from utils.data_generator import DataGenerator


ROOT = Path(__file__).resolve().parents[1]


class NbpSqrcMerchantDataTests(unittest.TestCase):
    def setUp(self):
        self.runner = SITRunner.__new__(SITRunner)
        self.runner.requests_dir = ROOT / "requests"
        self.runner.server_config = yaml.safe_load((ROOT / "config" / "servers.yaml").read_text(encoding="utf-8"))
        test_data = yaml.safe_load((ROOT / "config" / "test_data.yaml").read_text(encoding="utf-8"))
        self.runner.test_data_tokens = {str(key).upper(): str(value) for key, value in test_data.items() if value is not None}
        self.runner.receiving_bank = ""

    def render(self, api_name, request_file, bank="nbp", test_type="positive"):
        testcase = ServiceTestCase(
            tc_id="TC013",
            service="merchant_cas",
            description="SQRC merchant fixture",
            bank=bank,
            api_name=api_name,
            request_file=request_file,
            expected_result="SUCCESS",
            validation_type="response",
            execute="Y",
            test_type=test_type,
            trx_type="financial",
        )
        with patch.object(DataGenerator, "default_tokens", return_value={
            "RRN": "123456789012",
            "STAN": "123456",
            "DATETIME": "20260916150000",
        }):
            return self.runner._render_payload(
                request_file,
                extra_tokens={},
                service="merchant_cas",
                bank_name=bank,
                testcase=testcase,
            )

    def test_both_nbp_sqrc_apis_use_phc_merchant_and_nbp_sender(self):
        for api_name, request_file in (
            ("merchant_payment_direct_sqrc", "tc013.json"),
            ("merchant_payment_sqrc", "tc014.json"),
        ):
            with self.subTest(api=api_name):
                body = self.render(api_name, request_file)
                self.assertEqual(body["senderInfo"]["iban"], "PK69NBPA0071004245965806")
                self.assertEqual(body["merchantInfo"], {
                    "accountTitle": "PHC",
                    "dba": "PHC",
                    "categoryCode": "5271",
                    "bic": "NBPBPKKA",
                    "iban": "PK47NBPA0271003000011184",
                    "merchantIdAlias": "2608201125323506814",
                })
                self.assertEqual(body["additionalInfo"]["city"], "Karachi")
                self.assertEqual(body["additionalInfo"]["storeLabel"], "000920668378002")
                self.assertEqual(body["additionalInfo"]["terminalID"], "810001328")
                self.assertGreater(body["amountInfo"]["amount"], 0)

    def test_negative_missing_bic_remains_missing(self):
        body = self.render("merchant_payment_direct_sqrc", "tc027.json", test_type="negative")
        self.assertNotIn("bic", body["merchantInfo"])
        self.assertEqual(body["merchantInfo"]["accountTitle"], "PHC")

    def test_alias_and_other_banks_keep_their_merchant_data(self):
        alias = self.render("merchant_payment_alias", "nbp/tc015.json")
        dib_sqrc = self.render("merchant_payment_direct_sqrc", "tc013.json", bank="dib")
        self.assertEqual(alias["merchantInfo"]["bic"], self.runner.test_data_tokens["MERCHANT_BIC"])
        self.assertEqual(dib_sqrc["merchantInfo"]["bic"], self.runner.test_data_tokens["MERCHANT_BIC"])


if __name__ == "__main__":
    unittest.main()
