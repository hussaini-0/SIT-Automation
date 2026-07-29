"""Append 164 realistic testcase rows and matching request files."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "requests"
TESTCASES = ROOT / "testcases"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_rows(workbook_path: Path, sheet_name: str, rows: list[dict[str, str]]) -> None:
    workbook = load_workbook(workbook_path)
    sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    extra_headers = [header for row in rows for header in row if header not in headers]
    for header in dict.fromkeys(extra_headers):
        sheet.cell(1, len(headers) + 1).value = header
        headers.append(header)
    tc_id_index = headers.index("TC_ID") + 1 if "TC_ID" in headers else 1
    target_tc_ids = {str(row.get("TC_ID", "")).strip() for row in rows}
    for row_number in range(sheet.max_row, 1, -1):
        if str(sheet.cell(row_number, tc_id_index).value or "").strip() in target_tc_ids:
            sheet.delete_rows(row_number, 1)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    workbook.save(workbook_path)


def set_path(payload, path: str, value) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value


def add_acquiring_cases() -> int:
    rows: list[dict[str, str]] = []
    auth_base = load_json(REQUESTS / "acquiring" / "acq_001.json")
    txn_base = load_json(REQUESTS / "acquiring" / "acq_011.json")
    status_base = load_json(REQUESTS / "acquiring" / "acq_061.json")

    cases = []
    for field, value, expected, desc in [
        ("username", "", "400", "blank username"),
        ("username", None, "400", "null username"),
        ("password", "", "400", "blank password"),
        ("password", None, "400", "null password"),
        ("channel", "", "400", "blank channel"),
        ("channel", "invalid-channel", "401", "invalid channel"),
        ("username", "unknown_acq_user", "401", "invalid username"),
        ("password", "wrong_password", "401", "invalid password"),
        ("channel", "   ", "400", "whitespace channel"),
        ("username", "u" * 80, "400", "username too long"),
    ]:
        payload = copy.deepcopy(auth_base)
        payload[field] = value
        cases.append(("authenticate", payload, expected, f"Acquiring authentication {desc}", "status_code", "non-financial"))

    txn_mutations = [
        ("rrn", "", "400", "blank rrn"),
        ("rrn", "ABC", "400", "non numeric rrn"),
        ("rrn", "123", "400", "short rrn"),
        ("rrn", "1" * 30, "400", "long rrn"),
        ("stan", "", "400", "blank stan"),
        ("stan", "ABC123", "400", "non numeric stan"),
        ("stan", "12", "400", "short stan"),
        ("sender_iban", "", "400", "blank sender iban"),
        ("sender_iban", "PK00INVALID", "400", "invalid sender iban"),
        ("sender_idtype", "", "400", "blank sender id type"),
        ("sender_idtype", "PASSPORT", "400", "invalid sender id type"),
        ("sender_idvalue", "", "400", "blank sender id value"),
        ("sender_idvalue", "ABC", "400", "invalid sender id value"),
        ("receiver_iban", "", "400", "blank receiver iban"),
        ("receiver_iban", "PK00INVALID", "400", "invalid receiver iban"),
        ("receiver_participant_code", "", "400", "blank receiver participant code"),
        ("receiver_participant_code", "BAD", "400", "invalid receiver participant code"),
        ("amount", 0, "400", "zero amount"),
        ("amount", -1, "400", "negative amount"),
        ("amount", "ABC", "400", "invalid amount format"),
        ("amount", "10.999", "400", "amount more than two decimals"),
        ("fee", -1, "400", "negative fee"),
        ("transaction_date", "2026-99-99", "400", "invalid transaction date"),
        ("transaction_date", "", "400", "blank transaction date"),
        ("transaction_time", "256199", "400", "invalid transaction time"),
        ("transaction_time", "", "400", "blank transaction time"),
        ("payment_purpose", "", "400", "blank payment purpose"),
        ("payment_purpose", "9999", "400", "payment purpose too long"),
        ("narration", "", "400", "blank narration"),
        ("narration", "x" * 180, "400", "narration too long"),
        ("sender_name", "", "400", "blank sender name"),
        ("receiver_name", "", "400", "blank receiver name"),
        ("sender_idtype", None, "400", "null sender id type"),
        ("amount", None, "400", "null amount"),
        ("rrn", None, "400", "null rrn"),
    ]
    for field, value, expected, desc in txn_mutations:
        payload = copy.deepcopy(txn_base)
        payload[field] = value
        cases.append(("transaction", payload, expected, f"Acquiring transaction {desc}", "status_code", "financial"))

    for transaction_id, expected, desc in [
        ("", "400", "blank transaction id"),
        ("   ", "400", "whitespace transaction id"),
        ("ACQ-NOT-FOUND-0001", "404", "unknown transaction id"),
        ("INVALID/ID", "400", "invalid transaction id characters"),
        ("A" * 90, "400", "transaction id too long"),
        ("123", "400", "transaction id too short"),
        (None, "400", "null transaction id"),
        ("ACQ-STATUS-000000", "404", "status not found"),
        ("ACQ-STATUS-ABCDEF", "400", "non numeric status suffix"),
        ("ACQ_STATUS_000001", "400", "invalid separator"),
        ("ACQ-STATUS-", "400", "missing status suffix"),
        ("ACQ-STATUS-999999", "404", "future transaction id"),
        ("ACQ-STATUS-000061 ", "400", "trailing whitespace transaction id"),
        (" acq-status-000061", "400", "leading whitespace transaction id"),
        ("acq-status-000061", "400", "lowercase transaction id"),
    ]:
        payload = copy.deepcopy(status_base)
        payload["transaction_id"] = transaction_id
        cases.append(("transaction_status", payload, expected, f"Acquiring status {desc}", "status_code", "non-financial"))

    for offset, (api, payload, expected, desc, validation, trx_type) in enumerate(cases, start=76):
        request_name = f"acq_{offset:03d}.json"
        write_json(REQUESTS / "acquiring" / request_name, payload)
        rows.append(
            {
                "TC_ID": f"ACQTC{offset:03d}",
                "Description": desc,
                "Bank": "bank1",
                "API_Name": api,
                "Request_File": request_name,
                "Expected_Result": expected,
                "Validation_Type": validation,
                "Execute (Y/N)": "Y",
                "Flow_Config": "",
                "Validation_Rules": "",
                "Test_Type": "negative",
                "Trx_type": trx_type,
            }
        )

    append_rows(TESTCASES / "sit_testcases_acquiring.xlsx", "ACQUIRING", rows)
    return len(rows)


def add_merchant_positive_cases() -> int:
    rows: list[dict[str, str]] = []
    api_sources = [
        ("merchant_payment_direct_sqrc", "tc013.json", 8, "Direct SQRC"),
        ("merchant_payment_sqrc", "tc014.json", 8, "SQRC"),
        ("merchant_payment_alias", "tc015.json", 8, "Alias"),
        ("merchant_payment_direct_rtpn", "tc016.json", 7, "Direct RTPN"),
        ("merchant_payment_direct_rtpl", "tc017.json", 7, "Direct RTPL"),
        ("merchant_payment_direct_dqrc", "tc018.json", 6, "Direct DQRC"),
    ]
    tc_number = 169
    for api, source_file, count, label in api_sources:
        base = load_json(REQUESTS / "merchant_cas" / source_file)
        for variant in range(1, count + 1):
            payload = copy.deepcopy(base)
            amount = float(5 + variant)
            set_path(payload, "amountInfo.amount", amount)
            set_path(payload, "amountInfo.totalAmount", str(int(amount)))
            set_path(payload, "additionalInfo.billNumber", f"BILL-{tc_number:03d}")
            set_path(payload, "additionalInfo.customerLabel", f"QA-CUST-{tc_number:03d}")
            set_path(payload, "additionalInfo.referenceLabel", f"REF-{tc_number:03d}")
            if "rtp" in api or "dqrc" in api:
                set_path(payload, "additionalInfo.rtpId", "${RTP_ID}")
            request_name = f"tc{tc_number}.json"
            write_json(REQUESTS / "merchant_cas" / request_name, payload)
            rows.append(
                {
                    "TC_ID": f"TC{tc_number}",
                    "Description": f"Merchant {label} valid payment amount variant {variant:02d}",
                    "Bank": "bank1",
                    "API_Name": api,
                    "Request_File": request_name,
                    "Expected_Result": "SUCCESS",
                    "Validation_Type": "response",
                    "Execute (Y/N)": "Y",
                    "Flow_Config": "",
                    "Validation_Rules": "",
                    "Test_Type": "positive",
                    "Trx_type": "financial",
                }
            )
            tc_number += 1

    append_rows(TESTCASES / "sit_testcases_merchant_cas.xlsx", "MERCHANT_CAS", rows)
    return len(rows)


def add_mpg_cases() -> int:
    rows: list[dict[str, str]] = []
    templates = [
        ("paymentUsingPOST", "mpg_payment_v1_positive_standard.json", "Financial", "BatchInformation.BatchDetail.0.Amount", [1, 50, 100, 250, 999]),
        ("paymentUsingPOST_1", "mpg_payment_v2_positive_standard.json", "Financial", "BatchInformation.BatchDetail.0.Amount", [1, 50, 100, 250, 999]),
        ("validateUsingPOST", "mpg_validate_positive_standard.json", "Non-financial", "BatchInformation.BatchDetail.0.Amount", [1, 50, 100, 250, 999]),
        ("paymentInquiryUsingPOST", "mpg_payment_inquiry_positive_standard.json", "Non-financial", "BatchDateTime", ["20260724103000", "20260724103100", "20260724103200", "20260724103300", "20260724103400"]),
        ("paymentInquiryV2UsingPOST", "mpg_payment_inquiry_v2_positive_standard.json", "Non-financial", "DateTime", ["2026-07-24", "2026-07-25", "2026-07-26", "2026-07-27", "2026-07-28"]),
        ("prevalInquiryUsingPOST", "mpg_preval_inquiry_positive_standard.json", "Non-financial", "DateTime", ["2026-07-24", "2026-07-25", "2026-07-26", "2026-07-27", "2026-07-28"]),
        ("resendingPrevalOrPaymentUsingPOST", "mpg_resend_positive_standard.json", "Non-financial", "requestType", ["PREVALIDATION", "PAYMENT", "PREVALIDATION", "PAYMENT", "PREVALIDATION"]),
        ("getBatchUsingGET", "mpg_get_batch_positive_standard.json", "Non-financial", "BatchId", ["NBPA012411765307480277638", "NBPA012411765307480277639", "NBPA012411765307480277640", "NBPA012411765307480277641", "NBPA012411765307480277642"]),
    ]
    tc_number = 2437
    for api, source_file, trx_type, path, values in templates:
        base = load_json(REQUESTS / "mpg_sender_api" / source_file)
        for variant, value in enumerate(values, start=1):
            payload = copy.deepcopy(base)
            set_path(payload, path, value)
            if isinstance(payload, dict):
                if "TransactionInfo" in payload:
                    payload["TransactionInfo"]["RRN"] = "${RRN}"
                    payload["TransactionInfo"]["STAN"] = "${STAN}"
                if "RRN" in payload:
                    payload["RRN"] = "${RRN}"
                if "STAN" in payload:
                    payload["STAN"] = "${STAN}"
            request_name = f"mpg_realistic_{tc_number}.json"
            write_json(REQUESTS / "mpg_sender_api" / request_name, payload)
            rows.append(
                {
                    "TC_ID": f"MPGTC{tc_number}",
                    "Service": "mpg_sender_api",
                    "Description": f"MPG {api} realistic valid variant {variant:02d}",
                    "Bank": "bank1",
                    "API_Name": api,
                    "Request_File": request_name,
                    "Expected_Result": "success",
                    "Validation_Type": "response",
                    "Execute (Y/N)": "Y",
                    "Flow_Config": "",
                    "Validation_Rules": "",
                    "Test_Type": "positive",
                    "Trx_type": trx_type.lower(),
                }
            )
            tc_number += 1

    append_rows(TESTCASES / "sit_testcases_mpg_sender_api.xlsx", "MPG_SENDER_API", rows)
    return len(rows)


def add_cas_cases() -> int:
    rows: list[dict[str, str]] = []
    cases = []
    base_payment = load_json(REQUESTS / "cas" / "tc008.json")
    base_title = load_json(REQUESTS / "cas" / "tc004.json")
    base_register = load_json(REQUESTS / "cas" / "tc011.json")
    base_status = load_json(REQUESTS / "cas" / "tc012.json")

    for amount in [1, 10, 25, 75, 500]:
        payload = copy.deepcopy(base_payment)
        payload["amount"] = amount
        payload["narration"] = f"CAS payment amount boundary {amount}"
        cases.append(("payment", payload, "SUCCESS", "response", "positive", "financial", f"CAS payment valid amount {amount}"))
    for iban in ["${RECEIVER_IBAN}", "${IBAN_2}", "${TITLE_FETCH_WITH_PAYMENT_IBAN}", "${TIMEOUT_IBAN}", "${FAILED_IBAN}"]:
        payload = copy.deepcopy(base_title)
        payload["iban"] = iban
        cases.append(("titlefetch", payload, "SUCCESS", "response", "positive", "non-financial", f"CAS titlefetch valid configured IBAN {iban}"))
    for field, value, expected, desc in [
        ("documentNumber", "", "Please provide documentNumber", "blank document number"),
        ("name", "A", "name size must be between 2 and 140", "name too short"),
        ("surname", "B", "surname size must be between 2 and 140", "surname too short"),
        ("birthDate", "2026-99-99", "Invalid birthDate", "invalid birth date"),
        ("gender", "UNKNOWN", "Invalid gender", "invalid gender"),
    ]:
        payload = copy.deepcopy(base_register)
        payload[field] = value
        cases.append(("registerCustomer", payload, expected, "response", "negative", "non-financial", f"CAS register customer {desc}"))
    for field, value, expected, desc in [
        ("uid.value", "", "Please provide uid value", "blank uid value"),
        ("uid.type", "", "Please provide uid type", "blank uid type"),
        ("status", "", "Please provide status", "blank status"),
        ("stan", "ABC", "Stan: Only numeric value allowed", "non numeric stan"),
        ("rrn", "ABC", "Rrn: Only numeric value allowed", "non numeric rrn"),
    ]:
        payload = copy.deepcopy(base_status)
        set_path(payload, field, value)
        cases.append(("updatestatus", payload, expected, "response", "negative", "non-financial", f"CAS update status {desc}"))

    for offset, (api, payload, expected, validation, test_type, trx_type, desc) in enumerate(cases, start=435):
        request_name = f"tc_{offset}.json"
        write_json(REQUESTS / "cas" / request_name, payload)
        rows.append(
            {
                "TC_ID": f"TC{offset}",
                "Description": desc,
                "Bank": "bank1",
                "API_Name": api,
                "Request_File": request_name,
                "Expected_Result": expected,
                "Validation_Type": validation,
                "Execute (Y/N)": "Y",
                "Flow_Config": "",
                "Validation_Rules": "",
                "Test_Type": test_type,
                "Trx_type": trx_type,
            }
        )

    append_rows(TESTCASES / "sit_testcases.xlsx", "SIT", rows)
    return len(rows)


def main() -> None:
    counts = {
        "acquiring": add_acquiring_cases(),
        "merchant_cas": add_merchant_positive_cases(),
        "mpg_sender_api": add_mpg_cases(),
        "cas": add_cas_cases(),
    }
    total = sum(counts.values())
    print(counts)
    print(f"added={total}")
    if total != 164:
        raise SystemExit(f"Expected to add 164 cases, added {total}")


if __name__ == "__main__":
    main()
