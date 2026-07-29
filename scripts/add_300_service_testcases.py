from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
BATCH_NOT_FOUND = '404 NOT_FOUND "Batch not found"'


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def set_if_exists(payload: Any, dotted_path: str, value: Any) -> bool:
    current = payload
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        token: int | str = int(part) if part.isdigit() else part
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return False
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]

    last = int(parts[-1]) if parts[-1].isdigit() else parts[-1]
    if isinstance(last, int):
        if not isinstance(current, list) or last >= len(current):
            return False
        current[last] = value
        return True
    if not isinstance(current, dict) or last not in current:
        return False
    current[last] = value
    return True


def workbook_headers(path: Path) -> tuple[Any, Any, list[str]]:
    workbook = load_workbook(path)
    sheet = workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    return workbook, sheet, headers


def replace_generated_rows(path: Path, tc_ids: set[str], rows: list[dict[str, Any]]) -> None:
    workbook, sheet, headers = workbook_headers(path)
    tc_col = headers.index("TC_ID") + 1
    for row_number in range(sheet.max_row, 1, -1):
        tc_id = str(sheet.cell(row=row_number, column=tc_col).value or "").strip()
        if tc_id in tc_ids:
            sheet.delete_rows(row_number, 1)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    workbook.save(path)


def existing_rows(path: Path) -> list[dict[str, Any]]:
    workbook, sheet, headers = workbook_headers(path)
    rows: list[dict[str, Any]] = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if any(values):
            rows.append({headers[index]: values[index] if index < len(values) else "" for index in range(len(headers))})
    workbook.close()
    return rows


def normalize_row(row: dict[str, Any], headers: list[str]) -> dict[str, Any]:
    return {header: row.get(header, "") for header in headers}


def clone_manual_cases(
    *,
    workbook_path: Path,
    request_dir: Path,
    source_filter,
    count: int,
    id_start: int,
    id_prefix: str,
    file_pattern,
    description_prefix: str,
) -> int:
    workbook, sheet, headers = workbook_headers(workbook_path)
    workbook.close()
    sources = [row for row in existing_rows(workbook_path) if source_filter(row)]
    if not sources:
        raise ValueError(f"No source rows found in {workbook_path}")

    rows: list[dict[str, Any]] = []
    tc_ids: set[str] = set()
    for offset in range(count):
        source = sources[offset % len(sources)]
        tc_number = id_start + offset
        tc_id = f"{id_prefix}{tc_number:03d}" if id_prefix else f"TC{tc_number:03d}"
        request_file = file_pattern(tc_number)
        source_file = request_dir / str(source["Request_File"]).strip()
        payload = copy.deepcopy(load_json(source_file))

        marker = f"extended-{tc_number:03d}"
        set_if_exists(payload, "narration", marker)
        set_if_exists(payload, "reserveFields.r5", marker)
        set_if_exists(payload, "additionalInfo.referenceLabel", marker)
        set_if_exists(payload, "TransactionInfo.Additional_data2", marker)
        set_if_exists(payload, "BatchInformation.BatchDetail.0.reserver_field2", marker)

        write_json(request_dir / request_file, payload)
        generated = dict(source)
        generated["TC_ID"] = tc_id
        generated["Description"] = f"{description_prefix} {offset + 1:03d} - {source.get('Description', '')}"
        generated["Request_File"] = request_file
        generated["Execute (Y/N)"] = "Y"
        rows.append(normalize_row(generated, headers))
        tc_ids.add(tc_id)

    replace_generated_rows(workbook_path, tc_ids, rows)
    return len(rows)


def add_acquiring_cases() -> int:
    workbook_path = ROOT / "testcases" / "sit_testcases_acquiring.xlsx"
    request_dir = ROOT / "requests" / "acquiring"
    workbook, sheet, headers = workbook_headers(workbook_path)
    workbook.close()
    rows: list[dict[str, Any]] = []
    tc_ids: set[str] = set()

    auth_template = load_json(request_dir / "tc001.json")
    transaction_template = load_json(request_dir / "tc002.json")
    status_template = {"transaction_id": "${TRANSACTION_ID}"}

    for index in range(75):
        tc_id = f"ACQTC{index + 1:03d}"
        request_file = f"acq_{index + 1:03d}.json"
        tc_ids.add(tc_id)
        if index < 10:
            payload = copy.deepcopy(auth_template)
            payload["channel"] = "test" if index % 2 == 0 else "ib"
            api_name = "authenticate"
            description = f"Acquiring authentication valid channel variant {index + 1:03d}"
            trx_type = "non-financial"
        elif index < 60:
            payload = copy.deepcopy(transaction_template)
            amount = 100 + index
            set_if_exists(payload, "amount", amount)
            set_if_exists(payload, "fee", 0)
            set_if_exists(payload, "narration", f"Acquiring regression {index + 1:03d}")
            api_name = "transaction"
            description = f"Acquiring transaction valid amount variant {index - 9:03d}"
            trx_type = "financial"
        else:
            payload = copy.deepcopy(status_template)
            payload["transaction_id"] = f"ACQ-STATUS-{index + 1:06d}"
            api_name = "transaction_status"
            description = f"Acquiring transaction status lookup variant {index - 59:03d}"
            trx_type = "non-financial"

        write_json(request_dir / request_file, payload)
        row = {
            "TC_ID": tc_id,
            "Description": description,
            "Bank": "bank1",
            "API_Name": api_name,
            "Request_File": request_file,
            "Expected_Result": "200",
            "Validation_Type": "status_code",
            "Execute (Y/N)": "Y",
            "Flow_Config": "",
            "Validation_Rules": "",
            "Trx_type": trx_type,
        }
        rows.append(normalize_row(row, headers))

    replace_generated_rows(workbook_path, tc_ids, rows)
    return len(rows)


def add_mpg_cases() -> int:
    workbook_path = ROOT / "testcases" / "sit_testcases_mpg_sender_api.xlsx"
    request_dir = ROOT / "requests" / "mpg_sender_api"
    workbook, sheet, headers = workbook_headers(workbook_path)
    workbook.close()

    templates = [
        ("paymentUsingPOST", "Payment", "mpg_payment_v1_positive_standard.json", "financial"),
        ("validateUsingPOST", "Prevalidation", "mpg_validate_positive_standard.json", "financial"),
        ("paymentUsingPOST_1", "Payment V2", "mpg_payment_v2_positive_standard.json", "financial"),
        ("paymentInquiryUsingPOST", "Payment Inquiry", "mpg_payment_inquiry_positive_standard.json", "non-financial"),
        ("paymentInquiryV2UsingPOST", "Payment Inquiry V2", "mpg_payment_inquiry_v2_positive_standard.json", "non-financial"),
        ("prevalInquiryUsingPOST", "Prevalidation Inquiry", "mpg_preval_inquiry_positive_standard.json", "non-financial"),
        ("resendingPrevalOrPaymentUsingPOST", "Resend Prevalidation or Payment", "mpg_resend_positive_standard.json", "non-financial"),
        ("getBatchDetailsUsingGET", "Get Batch Details", "mpg_get_batch_details_positive_standard.json", "non-financial"),
        ("getBatchUsingGET", "Get Batch", "mpg_get_batch_positive_standard.json", "non-financial"),
    ]

    rows: list[dict[str, Any]] = []
    tc_ids: set[str] = set()
    for offset in range(75):
        api_name, label, template_file, trx_type = templates[offset % len(templates)]
        tc_id = f"MPGTC{2100 + offset}"
        request_file = f"mpg_extended_{offset + 1:03d}.json"
        payload = copy.deepcopy(load_json(request_dir / template_file))
        marker = f"mpg-extended-{offset + 1:03d}"
        set_if_exists(payload, "TransactionInfo.Additional_data2", marker)
        set_if_exists(payload, "BatchInformation.BatchDetail.0.reserver_field2", marker)
        if api_name in {"paymentUsingPOST", "validateUsingPOST", "paymentUsingPOST_1"}:
            set_if_exists(payload, "BatchInformation.BatchId", f"NBPA01241176530748027{7638 + offset:04d}"[:30])
        write_json(request_dir / request_file, payload)
        rows.append(
            normalize_row(
                {
                    "TC_ID": tc_id,
                    "Service": "mpg_sender_api",
                    "Description": f"{label} valid regression variant {offset + 1:03d}",
                    "Bank": "bank1",
                    "API_Name": api_name,
                    "Request_File": request_file,
                    "Expected_Result": "200",
                    "Validation_Type": "status_code",
                    "Execute (Y/N)": "Y",
                    "Flow_Config": "",
                    "Validation_Rules": "",
                    "Test_Type": "positive",
                    "Trx_type": trx_type,
                },
                headers,
            )
        )
        tc_ids.add(tc_id)

    replace_generated_rows(workbook_path, tc_ids, rows)
    return len(rows)


def main() -> None:
    counts = {
        "cas": clone_manual_cases(
            workbook_path=ROOT / "testcases" / "sit_testcases.xlsx",
            request_dir=ROOT / "requests" / "cas",
            source_filter=lambda row: str(row.get("TC_ID", "")).startswith("TC")
            and str(row.get("Request_File", "")).startswith("tc_")
            and int("".join(ch for ch in str(row.get("TC_ID", "")) if ch.isdigit()) or 0) >= 250,
            count=75,
            id_start=360,
            id_prefix="TC",
            file_pattern=lambda number: f"tc_{number}.json",
            description_prefix="CAS extended regression",
        ),
        "merchant_cas": clone_manual_cases(
            workbook_path=ROOT / "testcases" / "sit_testcases_merchant_cas.xlsx",
            request_dir=ROOT / "requests" / "merchant_cas",
            source_filter=lambda row: str(row.get("TC_ID", "")).startswith("TC")
            and int("".join(ch for ch in str(row.get("TC_ID", "")) if ch.isdigit()) or 0) >= 19,
            count=75,
            id_start=94,
            id_prefix="TC",
            file_pattern=lambda number: f"tc{number:03d}.json",
            description_prefix="Merchant CAS extended regression",
        ),
        "acquiring": add_acquiring_cases(),
        "mpg_sender_api": add_mpg_cases(),
    }
    print("Added service testcase rows:")
    for service, count in counts.items():
        print(f"- {service}: {count}")
    print(f"Total: {sum(counts.values())}")


if __name__ == "__main__":
    main()
