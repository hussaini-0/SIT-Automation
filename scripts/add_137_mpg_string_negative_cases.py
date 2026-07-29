from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = ROOT / "testcases" / "sit_testcases_mpg_sender_api.xlsx"
REQUEST_DIR = ROOT / "requests" / "mpg_sender_api"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def set_path(payload: Any, dotted_path: str, value: Any) -> None:
    current = payload
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        token: int | str = int(part) if part.isdigit() else part
        current = current[token]
    last: int | str = int(parts[-1]) if parts[-1].isdigit() else parts[-1]
    current[last] = value


def workbook_headers() -> tuple[Any, Any, list[str]]:
    workbook = load_workbook(WORKBOOK_PATH)
    sheet = workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    return workbook, sheet, headers


def normalize_row(row: dict[str, Any], headers: list[str]) -> dict[str, Any]:
    return {header: row.get(header, "") for header in headers}


def replace_generated_rows(rows: list[dict[str, Any]], tc_ids: set[str]) -> None:
    workbook, sheet, headers = workbook_headers()
    tc_col = headers.index("TC_ID") + 1
    for row_number in range(sheet.max_row, 1, -1):
        tc_id = str(sheet.cell(row=row_number, column=tc_col).value or "").strip()
        if tc_id in tc_ids:
            sheet.delete_rows(row_number, 1)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    workbook.save(WORKBOOK_PATH)


def case_specs() -> list[dict[str, str]]:
    ymdhms = "Date Time must be Formatted like this yyyyMMddHHmmss"
    ymd = "Date Time must be formatted like this yyyy-MM-dd"
    batch_len = "Batch ID limit min(24)|max(30)"
    tracking_len_31 = "Tracking ID limit min(24)|max(31)"
    tracking_len_30 = "Tracking ID limit min(24)|max(30)"

    return [
        {
            "api": "createAuthenticationTokenUsingPOST",
            "label": "Authentication",
            "template": "mpg_auth_positive_standard.json",
            "trx_type": "non-financial",
            "path": "username",
            "field": "username",
            "expected": "Invalid IP Address",
            "values": ["", "   ", "invalid_user", "user@example.com", "DIB", "this_username_is_far_too_long_for_validation_testing_1234567890"],
        },
        {
            "api": "createAuthenticationTokenUsingPOST",
            "label": "Authentication",
            "template": "mpg_auth_positive_standard.json",
            "trx_type": "non-financial",
            "path": "password",
            "field": "password",
            "expected": "Invalid IP Address",
            "values": ["", "   ", "x", "invalid_password", "password-with-symbols-@@@", "DIB", "this_password_is_far_too_long_for_validation_testing_1234567890"],
        },
        {
            "api": "createAuthenticationTokenUsingPOST",
            "label": "Authentication",
            "template": "mpg_auth_positive_standard.json",
            "trx_type": "non-financial",
            "path": "channel",
            "field": "channel",
            "expected": "Invalid channel",
            "values": ["", "   ", "mobile", "abc", "TEST", "prod", "channel_value_far_too_long_for_validation_testing"],
        },
        *mpg_financial_specs("paymentUsingPOST", "Payment", "mpg_payment_v1_positive_standard.json", ymdhms, batch_len, tracking_len_31),
        *mpg_financial_specs("validateUsingPOST", "Prevalidation", "mpg_validate_positive_standard.json", ymdhms, batch_len, tracking_len_31),
        *mpg_financial_specs("paymentUsingPOST_1", "Payment V2", "mpg_payment_v2_positive_standard.json", ymdhms, batch_len, tracking_len_31),
        {
            "api": "paymentInquiryUsingPOST",
            "label": "Payment inquiry",
            "template": "mpg_payment_inquiry_positive_standard.json",
            "trx_type": "non-financial",
            "path": "BatchId",
            "field": "BatchId",
            "expected": batch_len,
            "values": ["", "   ", "ABC", "123", "00000000000000000000000", "NBPA012411765307480277638_TOO_LONG", "NBPA012411765307480277638999"],
        },
        {
            "api": "paymentInquiryUsingPOST",
            "label": "Payment inquiry",
            "template": "mpg_payment_inquiry_positive_standard.json",
            "trx_type": "non-financial",
            "path": "BatchDateTime",
            "field": "BatchDateTime",
            "expected": ymdhms,
            "values": ["", "   ", "2026-07-24", "2026-99-99T25:61:61", "20261301120000", "20260732240000", "ABC"],
        },
        {
            "api": "paymentInquiryUsingPOST",
            "label": "Payment inquiry",
            "template": "mpg_payment_inquiry_positive_standard.json",
            "trx_type": "non-financial",
            "path": "TrackingId",
            "field": "TrackingId",
            "expected": tracking_len_30,
            "values": ["", "   ", "ABC", "123", "TRK202607241530000000", "TRK202607241530000000001_TOO_LONG", "TRK202607241530000000001999"],
        },
        *mpg_ymd_inquiry_specs("paymentInquiryV2UsingPOST", "Payment inquiry V2", "mpg_payment_inquiry_v2_positive_standard.json", ymd, batch_len),
        *mpg_ymd_inquiry_specs("prevalInquiryUsingPOST", "Prevalidation inquiry", "mpg_preval_inquiry_positive_standard.json", ymd, batch_len),
        {
            "api": "resendingPrevalOrPaymentUsingPOST",
            "label": "Resend prevalidation or payment",
            "template": "mpg_resend_positive_standard.json",
            "trx_type": "non-financial",
            "path": "BatchId",
            "field": "BatchId",
            "expected": batch_len,
            "values": ["", "   ", "ABC", "123", "00000000000000000000000", "NBPA012411765307480277638_TOO_LONG", "NBPA012411765307480277638999"],
        },
        {
            "api": "resendingPrevalOrPaymentUsingPOST",
            "label": "Resend prevalidation or payment",
            "template": "mpg_resend_positive_standard.json",
            "trx_type": "non-financial",
            "path": "DateTime",
            "field": "DateTime",
            "expected": ymdhms,
            "values": ["", "   ", "2026-07-24", "2026-99-99T25:61:61", "20261301120000", "ABC"],
        },
        {
            "api": "resendingPrevalOrPaymentUsingPOST",
            "label": "Resend prevalidation or payment",
            "template": "mpg_resend_positive_standard.json",
            "trx_type": "non-financial",
            "path": "requestType",
            "field": "requestType",
            "expected": "Invalid request type",
            "values": ["", "   ", "INVALID", "PAYMENTX", "FEDERATED_TOO_LONG"],
        },
    ]


def mpg_financial_specs(
    api: str,
    label: str,
    template: str,
    datetime_expected: str,
    batch_expected: str,
    tracking_expected: str,
) -> list[dict[str, str]]:
    return [
        {
            "api": api,
            "label": label,
            "template": template,
            "trx_type": "financial",
            "path": "TransactionInfo.DateTime",
            "field": "DateTime",
            "expected": datetime_expected,
            "values": ["", "   ", "2026-07-24", "2026-99-99T25:61:61", "20261301120000", "ABC"],
        },
        {
            "api": api,
            "label": label,
            "template": template,
            "trx_type": "financial",
            "path": "BatchInformation.BatchId",
            "field": "BatchId",
            "expected": batch_expected,
            "values": ["", "   ", "ABC", "123", "00000000000000000000000", "NBPA012411765307480277638_TOO_LONG"],
        },
        {
            "api": api,
            "label": label,
            "template": template,
            "trx_type": "financial",
            "path": "BatchInformation.BatchDetail.0.TrackingId",
            "field": "TrackingId",
            "expected": tracking_expected,
            "values": ["", "   ", "ABC", "123", "TRK202607241530000000", "TRK202607241530000000001_TOO_LONG"],
        },
    ]


def mpg_ymd_inquiry_specs(
    api: str,
    label: str,
    template: str,
    datetime_expected: str,
    batch_expected: str,
) -> list[dict[str, str]]:
    return [
        {
            "api": api,
            "label": label,
            "template": template,
            "trx_type": "non-financial",
            "path": "BatchId",
            "field": "BatchId",
            "expected": batch_expected,
            "values": ["", "   ", "ABC", "123", "00000000000000000000000", "NBPA012411765307480277638_TOO_LONG"],
        },
        {
            "api": api,
            "label": label,
            "template": template,
            "trx_type": "non-financial",
            "path": "DateTime",
            "field": "DateTime",
            "expected": datetime_expected,
            "values": ["", "   ", "20260724103500", "2026-99-99", "2026/07/24", "ABC"],
        },
    ]


def value_label(value: str) -> str:
    if value == "":
        return "empty"
    if value.strip() == "":
        return "blank"
    if value in {"ABC", "abc", "INVALID", "mobile"}:
        return "invalid"
    if value in {"123", "x"}:
        return "too short"
    if "TOO_LONG" in value or "far_too_long" in value:
        return "too long"
    if "99" in value or "-" in value:
        return "invalid format"
    return "invalid"


def main() -> None:
    _, _, headers = workbook_headers()
    rows: list[dict[str, Any]] = []
    tc_ids: set[str] = set()
    specs = case_specs()

    case_number = 0
    for spec in specs:
        for value in spec["values"]:
            if case_number >= 137:
                break
            case_number += 1
            tc_id = f"MPGTC{2299 + case_number}"
            request_file = f"mpg_string_negative_{case_number:03d}.json"
            payload = copy.deepcopy(load_json(REQUEST_DIR / spec["template"]))
            set_path(payload, spec["path"], value)
            write_json(REQUEST_DIR / request_file, payload)

            rows.append(
                normalize_row(
                    {
                        "TC_ID": tc_id,
                        "Service": "mpg_sender_api",
                        "Description": f"{spec['label']} {value_label(value)} {spec['field']}",
                        "Bank": "bank1",
                        "API_Name": spec["api"],
                        "Request_File": request_file,
                        "Expected_Result": spec["expected"],
                        "Validation_Type": "response",
                        "Execute (Y/N)": "Y",
                        "Flow_Config": "",
                        "Validation_Rules": "",
                        "Test_Type": "negative",
                        "Trx_type": spec["trx_type"],
                    },
                    headers,
                )
            )
            tc_ids.add(tc_id)
        if case_number >= 137:
            break

    if case_number != 137:
        raise RuntimeError(f"Expected to generate 137 cases, generated {case_number}")

    replace_generated_rows(rows, tc_ids)
    print(f"Added MPG string negative cases: {case_number}")
    print(f"ID range: MPGTC2300-MPGTC2436")


if __name__ == "__main__":
    main()
