import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from runner import SITRunner
from services import execution_service
from testcase_models import ServiceTestCase


def case(tc_id, api_name, test_type="positive"):
    return ServiceTestCase(
        tc_id=tc_id,
        service="merchant_cas",
        description=tc_id,
        bank="nbp",
        api_name=api_name,
        request_file="tc001.json",
        expected_result="SUCCESS",
        validation_type="response",
        execute="Y",
        test_type=test_type,
        trx_type="financial",
    )


class AuthPreflightOrderTests(unittest.TestCase):
    def test_preflight_stops_full_run_on_rate_limited_ib_auth(self):
        runner = SITRunner.__new__(SITRunner)
        runner._auth_api_names = Mock(return_value=["authenticate"])
        auth = case("TC002", "authenticate")
        runner._bootstrap_reusable_auth_tokens = Mock(return_value=[
            (auth, {"status": "FAILED", "status_code": 429, "actual": "HTTP 429"})
        ])
        runner._get_token_for_api = Mock(return_value="")
        runner._extract_channel_key = Mock(return_value="ib")
        runner.service_manager = Mock()
        runner.service_manager.get_service_token_routing.return_value = {"merchant_payment_alias": "ib"}

        with self.assertRaisesRegex(RuntimeError, "auth token unavailable.*HTTP 429"):
            runner.prime_auth_tokens([case("TC015", "merchant_payment_alias")])

    def test_preflight_reuses_one_successful_auth_attempt(self):
        runner = SITRunner.__new__(SITRunner)
        runner._auth_api_names = Mock(return_value=["authenticate"])
        auth = case("TC002", "authenticate")
        attempted = [(auth, {"status": "PASSED", "status_code": 200})]
        runner._bootstrap_reusable_auth_tokens = Mock(return_value=attempted)
        runner._get_token_for_api = Mock(return_value="token")

        self.assertEqual(runner.prime_auth_tokens([case("TC015", "merchant_payment_alias")]), attempted)
        runner._bootstrap_reusable_auth_tokens.assert_called_once()

    def test_ui_runs_protected_api_before_negative_auth(self):
        auth = SimpleNamespace(service="merchant_cas", bank="nbp", tc_id="TC002", api_name="authenticate", test_type="positive")
        payment = SimpleNamespace(service="merchant_cas", bank="nbp", tc_id="TC015", api_name="merchant_payment_alias", test_type="positive")
        invalid_auth = SimpleNamespace(service="merchant_cas", bank="nbp", tc_id="TC004", api_name="authenticate", test_type="negative")
        state = execution_service.ExecutionState(job_id="test")
        options = execution_service.ExecutionOptions(services=["merchant_cas"], bank="nbp", parallel=False)
        events = []
        runner = Mock()
        runner.api_config = {"defaults": {}}
        runner._auth_api_names.return_value = ["authenticate"]
        runner.prime_auth_tokens.side_effect = lambda cases: events.append("prime") or [
            (auth, {"status": "PASSED", "tc_id": "TC002", "service": "merchant_cas"})
        ]
        runner.execute_testcase.side_effect = lambda record: (
            events.append(record.tc_id) or {"status": "PASSED", "tc_id": record.tc_id, "service": record.service}
        )
        runner._build_summary.return_value = {"total": 3, "passed": 3, "failed": 0, "pass_percent": 100.0}
        runner._build_service_artifact_tag.return_value = "merchant-cas"
        runner._artifact_file_name.return_value = "report.html"
        runner.reports_dir = Path("reports")
        runner.results_dir = Path("results")

        with patch.object(execution_service, "get_execution_state", return_value=state), \
             patch.object(execution_service, "SITRunner", return_value=runner), \
             patch.object(execution_service, "ApiClient"), \
             patch.object(execution_service, "_select_records", return_value=[auth, payment, invalid_auth]), \
             patch.object(execution_service, "to_runner_testcase", side_effect=lambda record: record), \
             patch.object(execution_service, "append_history"):
            execution_service._run_job("test", options)

        self.assertEqual(state.status, "completed")
        self.assertEqual(events, ["prime", "TC015", "TC004"])

    def test_cli_runs_protected_api_before_negative_auth(self):
        auth = case("TC002", "authenticate")
        payment = case("TC015", "merchant_payment_alias")
        invalid_auth = case("TC004", "authenticate", "negative")
        runner = SITRunner.__new__(SITRunner)
        runner.framework_logger = Mock()
        runner.load_testcases = Mock(return_value=[auth, payment, invalid_auth])
        runner._limit_negative_auth_attempts = Mock(side_effect=lambda cases, max_attempts: cases)
        runner._auth_api_names = Mock(return_value=["authenticate"])
        events = []
        runner.prime_auth_tokens = Mock(side_effect=lambda cases: events.append("prime") or [
            (auth, {"status": "PASSED", "tc_id": "TC002", "service": "merchant_cas"})
        ])
        runner._is_sequential_testcase = Mock(return_value=False)
        runner.execute_testcase = Mock(side_effect=lambda testcase: (
            events.append(testcase.tc_id) or {"status": "PASSED", "tc_id": testcase.tc_id, "service": testcase.service}
        ))
        runner._build_summary = Mock(return_value={"total": 3, "passed": 3})
        runner._build_service_artifact_tag = Mock(return_value="merchant-cas")
        runner._write_results_json = Mock()
        runner._write_results_csv = Mock()
        runner._write_html_report = Mock()

        runner.run(services=["merchant_cas"], banks=["nbp"], max_workers=1)

        self.assertEqual(events, ["prime", "TC015", "TC004"])


if __name__ == "__main__":
    unittest.main()
