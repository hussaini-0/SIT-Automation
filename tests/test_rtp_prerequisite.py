import unittest
from unittest.mock import Mock

from runner import SITRunner
from testcase_models import ServiceTestCase


class FakeApiClient:
    def __init__(self) -> None:
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        call_number = len(self.calls)
        return {
            "status_code": 200,
            "elapsed_ms": 5,
            "body": {
                "response_code": "00",
                "response_desc": "Success",
                "info": {"RTPId": f"fresh-rtp-{call_number}"},
            },
        }


class RTPPrerequisiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = SITRunner.__new__(SITRunner)
        self.runner.api_client = FakeApiClient()
        self.runner.framework_logger = Mock()
        self.runner.error_logger = Mock()
        self.runner.validator = Mock()
        self.runner.validator.validate.return_value = {"passed": True, "actual": "00"}
        self.runner._get_bank_base_url = Mock(return_value="http://bank")
        self.runner._build_request_headers = Mock(return_value={"Authorization": "Bearer token"})
        self.runner._render_payload = Mock(side_effect=self._render_payload)
        self.runner._get_api_definition = Mock(side_effect=self._api_definition)

    @staticmethod
    def _render_payload(request_file, **_kwargs):
        if request_file == "generateRTP.json":
            return {"info": {"rrn": "", "stan": ""}}
        return {"paymentDetails": {"RTPId": ""}, "info": {"rrn": "pay", "stan": "pay"}}

    @staticmethod
    def _api_definition(api_name, _service):
        if api_name == "generateRTP":
            return {"endpoint": "/generate", "method": "POST", "headers": {}}
        return {
            "endpoint": "/payment",
            "method": "POST",
            "headers": {},
            "prerequisite": {
                "api": "generateRTP",
                "request_file": "generateRTP.json",
                "success_codes": ["00"],
                "response_paths": ["info.RTPId"],
                "target_path": "paymentDetails.RTPId",
                "positive_only": True,
            },
        }

    @staticmethod
    def _testcase(test_type="positive"):
        return ServiceTestCase(
            tc_id="TC_RTP",
            service="acquiring",
            description="RTP payment",
            bank="nbp",
            api_name="RTPNow",
            request_file="RTPNow.json",
            expected_result="SUCCESS",
            validation_type="response",
            execute="Y",
            test_type=test_type,
            trx_type="financial",
        )

    def test_positive_payment_uses_fresh_generated_rtp_id(self):
        main_calls = []

        def call_main(**kwargs):
            main_calls.append(kwargs)
            return kwargs["payload"], {
                "status_code": 200,
                "elapsed_ms": 7,
                "body": {"response_code": "00", "response_desc": "Success"},
            }

        self.runner._call_api_with_account_fallback = call_main

        first = self.runner.execute_testcase(self._testcase(), capture_auth_token=False)
        second = self.runner.execute_testcase(self._testcase(), capture_auth_token=False)

        self.assertEqual("fresh-rtp-1", first["request_payload"]["payment"]["paymentDetails"]["RTPId"])
        self.assertEqual("fresh-rtp-2", second["request_payload"]["payment"]["paymentDetails"]["RTPId"])
        self.assertNotEqual(
            first["request_payload"]["prerequisite"]["info"]["rrn"],
            second["request_payload"]["prerequisite"]["info"]["rrn"],
        )
        self.assertEqual("generateRTP->RTPNow", first["api_name"])
        self.assertEqual(2, len(main_calls))

    def test_negative_rtp_id_case_keeps_its_original_payload(self):
        prerequisite = self.runner._execute_api_prerequisite(
            testcase=self._testcase(test_type="negative"),
            api_definition=self._api_definition("RTPNow", "acquiring"),
            bank_base_url="http://bank",
        )

        self.assertIsNone(prerequisite)
        self.assertEqual([], self.runner.api_client.calls)

    def test_payment_is_not_called_when_generate_rtp_fails(self):
        self.runner.api_client.call = Mock(
            return_value={
                "status_code": 200,
                "elapsed_ms": 5,
                "body": {"response_code": "068", "response_desc": "Duplicate Transaction"},
            }
        )
        self.runner._call_api_with_account_fallback = Mock()

        result = self.runner.execute_testcase(self._testcase(), capture_auth_token=False)

        self.assertEqual("FAILED", result["status"])
        self.assertIn("Prerequisite 'generateRTP' failed", result["error"])
        self.runner._call_api_with_account_fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
