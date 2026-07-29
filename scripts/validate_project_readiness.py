"""Validate testcase/config readiness without calling bank APIs."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict, replace
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.health_service import check_records_reachability
from services.testcase_service import filter_testcase_inventory, load_testcase_inventory
from services.testcase_validation_service import validate_records_for_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local readiness checks for SIT automation.")
    parser.add_argument("--service", action="append", default=[], help="Filter by service. Repeat as needed.")
    parser.add_argument("--api", action="append", default=[], help="Filter by API. Repeat as needed.")
    parser.add_argument("--tc", action="append", default=[], help="Filter by testcase ID. Repeat as needed.")
    parser.add_argument("--bank", default="", help="Override the Bank column with a configured bank profile.")
    parser.add_argument("--include-disabled", action="store_true", help="Include Execute=N testcase rows.")
    parser.add_argument("--check-network", action="store_true", help="Also check host/port reachability.")
    parser.add_argument("--timeout", type=int, default=3, help="Network check timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = filter_testcase_inventory(
        load_testcase_inventory(),
        services=args.service,
        apis=args.api,
        testcase_ids=args.tc,
        include_disabled=bool(args.include_disabled),
    )
    if args.bank.strip():
        records = [replace(record, bank=args.bank.strip()) for record in records]

    print(f"Selected testcases: {len(records)}")
    issues = validate_records_for_run(records)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        print(f"Validation errors: {len(errors)}")
        for issue in errors[:100]:
            data = asdict(issue)
            print(
                f"- {data['service']} | {data['bank']} | {data['tc_id']} | "
                f"{data['api_name']} | {data['message']}"
            )
    else:
        print("Validation errors: 0")

    network_failures = []
    if args.check_network:
        reachability = check_records_reachability(records, timeout_seconds=max(1, args.timeout))
        network_failures = [result for result in reachability if not result.reachable]
        print(f"Network targets checked: {len(reachability)}")
        for result in network_failures:
            print(f"- {result.service} | {result.bank} | {result.base_url} | {result.error}")

    return 1 if errors or network_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
