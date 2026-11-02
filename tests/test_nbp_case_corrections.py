import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml

from runner import SITRunner
from services import execution_service
from services.testcase_service import select_testcase_inventory
from testcase_models import ServiceTestCase
from utils.data_generator import DataGenerator


ROOT = Path(__file__).resolve().parents[1]


class NbpCaseCorrectionsTests(unittest.TestCase):
    def test_valid_cases_expect_business_success(self):
        expected_positive = {
            "TC002", "TC004", "TC008", "TC009", "TC027", "TC028", "TC029",
            "TC031", "TC032", "TC055", "TC056", "TC063", "TC078", "TC079",
            "TC094", "TC231", "TC435", "TC436", "TC437", "TC438", "TC439", "TC440",
        }
        cases = select_testcase_inventory(services=["cas"], banks=["nbp"])
        selected = {case.tc_id: case for case in cases if case.tc_id in expected_positive}
        self.assertEqual(set(selected), expected_positive)
        for case in selected.values():
            with self.subTest(tc_id=case.tc_id):
                self.assertEqual(case.test_type, "positive")
                self.assertEqual(case.expected_result, "00")
                self.assertEqual(case.validation_type, "json_field")
                self.assertEqual(json.loads(case.validation_rules)["field"], "response.response_code")

        unresolved_negative = {
            "TC068", "TC072", "TC073", "TC074", "TC081",
            "TC084", "TC085", "TC102", "TC105",
        }
        for case in cases:
            if case.tc_id in unresolved_negative:
                self.assertEqual(case.test_type, "negative", case.tc_id)

    def test_faysal_receiver_iban_uses_faysal_bic(self):
        for name in ("tc003.json", "tc005.json"):
            body = json.loads((ROOT / "requests" / "cas" / name).read_text(encoding="utf-8"))
            self.assertTrue(body["receiver_iban"].startswith("PK27FAYS"))
            self.assertEqual(body["receiver_participant_code"], "FAYSPKKA")

    def test_registered_uid_is_used_for_status_and_delete(self):
        runner = SITRunner.__new__(SITRunner)
        runner._registered_customer_uid = {}
        runner.requests_dir = ROOT / "requests"
        runner.server_config = yaml.safe_load((ROOT / "config" / "servers.yaml").read_text(encoding="utf-8"))
        runner.test_data_tokens = {"CNIC": "1117361039962"}
        runner.receiving_bank = ""

        registration = ServiceTestCase(
            tc_id="TC243", service="cas", description="Register customer", bank="nbp",
            api_name="registerCustomer", request_file="tc_243.json", expected_result="SUCCESS",
            validation_type="response", execute="Y", test_type="positive",
        )
        runner._capture_registered_customer_uid(registration, {
            "body": {"response": {"response_code": "00", "register-customer": {"uid": {"value": "4781234567890"}}}}
        })
        self.assertEqual(runner._registered_customer_uid["nbp"], "4781234567890")

        with patch.object(DataGenerator, "default_tokens", return_value={"RRN": "123456789012", "STAN": "123456"}):
            for tc_id, api_name, request_file in (
                ("TC012", "updatestatus", "tc012.json"),
                ("TC021", "deletecustomer", "tc020.json"),
            ):
                case = ServiceTestCase(
                    tc_id=tc_id, service="cas", description=api_name, bank="nbp",
                    api_name=api_name, request_file=request_file, expected_result="SUCCESS",
                    validation_type="response", execute="Y", test_type="positive",
                )
                body = runner._render_payload(request_file, {}, service="cas", bank_name="nbp", testcase=case)
                self.assertEqual(body["uid"]["value"], "4781234567890")

    def test_cli_orders_registration_before_customer_actions(self):
        cases = [
            ServiceTestCase(
                tc_id=tc_id, service="cas", description=tc_id, bank="nbp", api_name=api_name,
                request_file="tc001.json", expected_result="SUCCESS", validation_type="response",
                execute="Y", test_type="positive",
            )
            for tc_id, api_name in (
                ("TC012", "updatestatus"),
                ("TC021", "deletecustomer"),
                ("TC243", "registerCustomer"),
            )
        ]
        runner = SITRunner.__new__(SITRunner)
        runner.framework_logger = Mock()
        runner.load_testcases = Mock(return_value=cases)
        runner._limit_negative_auth_attempts = Mock(side_effect=lambda items, max_attempts: items)
        runner._auth_api_names = Mock(return_value=[])
        runner.prime_auth_tokens = Mock(return_value=[])
        runner.service_manager = Mock()
        events = []
        runner.execute_testcase = Mock(side_effect=lambda item: (
            events.append(item.tc_id) or {"status": "PASSED", "service": item.service, "tc_id": item.tc_id}
        ))
        runner._build_summary = Mock(return_value={"total": 3, "passed": 3})
        runner._build_service_artifact_tag = Mock(return_value="cas")
        runner._write_results_json = Mock()
        runner._write_results_csv = Mock()
        runner._write_html_report = Mock()

        runner.run(services=["cas"], banks=["nbp"], max_workers=1)
        self.assertEqual(events, ["TC243", "TC012", "TC021"])

    def test_ui_orders_registration_before_customer_actions(self):
        cases = [
            SimpleNamespace(
                tc_id=tc_id, service="cas", bank="nbp", api_name=api_name,
                test_type="positive", description=tc_id, trx_type="non-financial",
                expected_result="SUCCESS",
            )
            for tc_id, api_name in (
                ("TC012", "updatestatus"),
                ("TC021", "deletecustomer"),
                ("TC243", "registerCustomer"),
            )
        ]
        state = execution_service.ExecutionState(job_id="customer-chain")
        options = execution_service.ExecutionOptions(services=["cas"], bank="nbp", parallel=True)
        events = []
        runner = Mock()
        runner.api_config = {"defaults": {}}
        runner._auth_api_names.return_value = []
        runner.prime_auth_tokens.return_value = []
        runner.execute_testcase.side_effect = lambda case: (
            events.append(case.tc_id) or {"status": "PASSED", "tc_id": case.tc_id, "service": case.service}
        )
        runner._build_summary.return_value = {"total": 3, "passed": 3, "failed": 0}
        runner._build_service_artifact_tag.return_value = "cas"
        runner._artifact_file_name.return_value = "report.html"
        runner.reports_dir = Path("reports")
        runner.results_dir = Path("results")

        with patch.object(execution_service, "get_execution_state", return_value=state), \
             patch.object(execution_service, "SITRunner", return_value=runner), \
             patch.object(execution_service, "ApiClient"), \
             patch.object(execution_service, "_select_records", return_value=cases), \
             patch.object(execution_service, "to_runner_testcase", side_effect=lambda case: case), \
             patch.object(execution_service, "append_history"):
            execution_service._run_job("customer-chain", options)

        self.assertEqual(state.status, "completed")
        self.assertEqual(events, ["TC243", "TC012", "TC021"])


if __name__ == "__main__":
    unittest.main()
