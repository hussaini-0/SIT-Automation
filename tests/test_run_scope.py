import unittest
from types import SimpleNamespace

from services.testcase_service import scope_run_cases, select_testcase_inventory


class RunScopeTests(unittest.TestCase):
    def test_nbp_run_skips_rtp_and_keeps_two_register_cases(self):
        cases = select_testcase_inventory(
            services=["acquiring", "cas", "merchant_cas"],
            banks=["nbp"],
        )
        selected = scope_run_cases(cases, skip_rtp=True, register_customer_limit=2)

        self.assertFalse(any("rtp" in case.api_name.lower() for case in selected))
        self.assertEqual(
            [(case.tc_id, case.test_type) for case in selected if case.api_name == "registerCustomer"],
            [("TC243", "positive"), ("TC249", "negative")],
        )
        self.assertTrue(any(case.api_name == "merchant_payment_direct_sqrc" for case in selected))
        self.assertTrue(any(case.api_name == "merchant_payment_sqrc" for case in selected))

    def test_other_apis_and_case_order_remain_unchanged(self):
        def case(tc_id, api_name, test_type="positive"):
            return SimpleNamespace(
                tc_id=tc_id,
                api_name=api_name,
                service="cas",
                bank="nbp",
                test_type=test_type,
            )

        cases = [
            case("TC001", "payment"),
            case("TC011", "registerCustomer"),
            case("TC249", "registerCustomer", "negative"),
            case("TC243", "registerCustomer"),
            case("TC088", "RTPNow"),
            case("TC089", "titleFetch"),
        ]
        selected = scope_run_cases(cases, skip_rtp=True, register_customer_limit=2)
        self.assertEqual([item.tc_id for item in selected], ["TC001", "TC249", "TC243", "TC089"])


if __name__ == "__main__":
    unittest.main()
