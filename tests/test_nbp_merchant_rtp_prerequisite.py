import unittest
from pathlib import Path
from unittest.mock import Mock

import yaml

from runner import SITRunner
from testcase_models import ServiceTestCase


ROOT = Path(__file__).resolve().parents[1]


class NbpMerchantRtpPrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.runner = SITRunner.__new__(SITRunner)
        self.runner.framework_logger = Mock()
        self.runner.api_client = Mock()
        self.runner.api_client.call.return_value = {
            "status_code": 200,
            "elapsed_ms": 5,
            "body": {"response_code": "00", "info": {"RTPId": "generated-rtp-id-123456789"}},
        }
        self.runner._get_api_definition = Mock(
            return_value={"endpoint": "/generateRTP", "method": "POST", "headers": {}}
        )
        self.runner._render_payload = Mock(return_value={"info": {"rrn": "", "stan": ""}})
        self.runner._refresh_generated_transaction_fields = Mock(
            side_effect=lambda payload: payload["info"].update(rrn="123456789012", stan="123456")
        )
        self.runner._apply_endpoint_params = Mock(side_effect=lambda endpoint, _payload: endpoint)
        self.runner._render_config_text = Mock(side_effect=lambda value, _bank: value)
        self.runner._get_bank_base_url = Mock(return_value="http://nbp:9096")
        self.runner._build_url = Mock(side_effect=lambda base, endpoint: base + endpoint)
        self.runner._build_request_headers = Mock(return_value={"Authorization": "Bearer acquiring"})
        config = yaml.safe_load((ROOT / "config" / "apis.yaml").read_text(encoding="utf-8"))
        self.definition = config["services"]["merchant_cas"]["apis"]["merchant_payment_direct_rtpn"]

    @staticmethod
    def _testcase(tc_id="TC016", bank="nbp", test_type="positive"):
        return ServiceTestCase(
            tc_id=tc_id,
            service="merchant_cas",
            description="Merchant RTP payment",
            bank=bank,
            api_name="merchant_payment_direct_rtpn",
            request_file="nbp/tc016.json",
            expected_result="SUCCESS",
            validation_type="response",
            execute="Y",
            test_type=test_type,
            trx_type="financial",
        )

    def prerequisite(self, testcase):
        return self.runner._execute_api_prerequisite(
            testcase=testcase,
            api_definition=self.definition,
            bank_base_url="http://nbp:9093",
        )

    def test_nbp_uses_acquiring_service_and_base_url(self):
        result = self.prerequisite(self._testcase())

        self.assertTrue(result["passed"])
        self.assertEqual("generated-rtp-id-123456789", result["value"])
        self.assertEqual("additionalInfo.rtpId", result["target_path"])
        self.runner._get_api_definition.assert_called_once_with("RTPNow", "acquiring")
        self.runner._get_bank_base_url.assert_called_once_with("nbp", "acquiring")
        self.runner._build_request_headers.assert_called_once_with(
            {"endpoint": "/generateRTP", "method": "POST", "headers": {}},
            "RTPNow",
            "acquiring",
            "nbp",
        )
        self.assertEqual("http://nbp:9096/generateRTP", self.runner.api_client.call.call_args.kwargs["url"])

    def test_other_bank_does_not_use_nbp_prerequisite(self):
        self.assertIsNone(self.prerequisite(self._testcase(bank="dib")))
        self.runner.api_client.call.assert_not_called()

    def test_negative_field_case_gets_fresh_rtp(self):
        self.assertTrue(self.prerequisite(self._testcase(tc_id="TC052", test_type="negative"))["passed"])

    def test_missing_rtp_id_case_preserves_invalid_input(self):
        self.assertIsNone(self.prerequisite(self._testcase(tc_id="TC085", test_type="negative")))
        self.runner.api_client.call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
