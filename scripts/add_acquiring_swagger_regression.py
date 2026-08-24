from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = ROOT / "testcases" / "sit_testcases_acquiring.xlsx"
REQUEST_DIR = ROOT / "requests" / "acquiring"
SHEET_NAME = "ACQUIRING"
TC_PREFIX = "TC_SWAGGER_"
START_NUMBER = 174
REQUEST_PREFIX = "swagger_reg_"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "api"


def iter_leaf_paths(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(payload, dict):
        leaves: list[tuple[str, Any]] = []
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else key
            leaves.extend(iter_leaf_paths(value, path))
        return leaves
    if isinstance(payload, list):
        if not payload:
            return [(prefix, payload)]
        leaves = []
        for index, value in enumerate(payload):
            path = f"{prefix}.{index}" if prefix else str(index)
            leaves.extend(iter_leaf_paths(value, path))
        return leaves
    return [(prefix, payload)]


def path_tokens(path: str) -> list[str | int]:
    return [int(part) if part.isdigit() else part for part in path.split(".") if part]


def set_path(payload: Any, path: str, value: Any) -> None:
    current = payload
    tokens = path_tokens(path)
    for token in tokens[:-1]:
        current = current[token]
    current[tokens[-1]] = value


def remove_path(payload: Any, path: str) -> None:
    current = payload
    tokens = path_tokens(path)
    for token in tokens[:-1]:
        current = current[token]
    final = tokens[-1]
    if isinstance(current, list) and isinstance(final, int):
        current.pop(final)
    elif isinstance(current, dict):
        current.pop(final, None)


def field_score(path: str, value: Any) -> int:
    lowered = path.lower()
    score = 0
    for token in [
        "amount",
        "iban",
        "rrn",
        "stan",
        "date",
        "time",
        "currency",
        "memberid",
        "merchant",
        "payer",
        "id",
        "status",
        "alias",
        "account",
    ]:
        if token in lowered:
            score += 10
    if value in ("", 0, False, None):
        score += 1
    return score


def pick_primary_field(payload: Any) -> tuple[str, Any] | None:
    leaves = [(path, value) for path, value in iter_leaf_paths(payload) if path]
    if not leaves:
        return None
    return sorted(leaves, key=lambda item: field_score(item[0], item[1]), reverse=True)[0]


def pick_alternate_field(payload: Any, primary_path: str) -> tuple[str, Any] | None:
    leaves = [(path, value) for path, value in iter_leaf_paths(payload) if path and path != primary_path]
    if not leaves:
        return None
    return sorted(leaves, key=lambda item: field_score(item[0], item[1]), reverse=True)[0]


def invalid_value_for(path: str, current: Any) -> Any:
    lowered = path.lower()
    if "amount" in lowered:
        return "abc"
    if "date" in lowered:
        return "2026-99-99"
    if "time" in lowered:
        return "25:61:99"
    if "iban" in lowered:
        return "PK00INVALID"
    if "rrn" in lowered or "stan" in lowered:
        return "ABC"
    if "email" in lowered:
        return "invalid-email"
    if "lat" in lowered or "long" in lowered:
        return "abc"
    if isinstance(current, bool):
        return "not_boolean"
    if isinstance(current, (int, float)):
        return "abc"
    return "@@INVALID@@"


def boundary_value_for(path: str, current: Any) -> Any:
    lowered = path.lower()
    if "amount" in lowered or isinstance(current, (int, float)):
        return -1
    if "date" in lowered:
        return "1900-01-01"
    if "iban" in lowered:
        return "PK" + "9" * 40
    if isinstance(current, bool):
        return None
    return "X" * 256


def build_case_payload(base: Any, mutation: str, path: str, value: Any) -> Any:
    payload = copy.deepcopy(base)
    if mutation == "missing":
        remove_path(payload, path)
    elif mutation == "null":
        set_path(payload, path, None)
    elif mutation == "invalid":
        set_path(payload, path, invalid_value_for(path, value))
    elif mutation == "boundary":
        set_path(payload, path, boundary_value_for(path, value))
    else:
        raise ValueError(f"Unknown mutation: {mutation}")
    return payload


def load_swagger_rows(sheet: Any, headers: list[str]) -> list[dict[str, Any]]:
    idx = {header: index for index, header in enumerate(headers)}
    rows: list[dict[str, Any]] = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if not any(values):
            continue
        row = {header: values[index] if index < len(values) else "" for header, index in idx.items()}
        tc_id = str(row.get("TC_ID") or "")
        request_file = str(row.get("Request_File") or "")
        if tc_id.startswith(TC_PREFIX) and not request_file.startswith(REQUEST_PREFIX):
            rows.append(row)
    return rows


def remove_previous_generated(sheet: Any, headers: list[str]) -> None:
    tc_col = headers.index("TC_ID") + 1
    request_col = headers.index("Request_File") + 1
    for row_number in range(sheet.max_row, 1, -1):
        tc_id = str(sheet.cell(row=row_number, column=tc_col).value or "")
        request_file = str(sheet.cell(row=row_number, column=request_col).value or "")
        if tc_id.startswith(TC_PREFIX) and request_file.startswith(REQUEST_PREFIX):
            sheet.delete_rows(row_number, 1)
    for path in REQUEST_DIR.glob(f"{REQUEST_PREFIX}*.json"):
        path.unlink()


def main() -> None:
    workbook = load_workbook(WORKBOOK_PATH)
    sheet = workbook[SHEET_NAME] if SHEET_NAME in workbook.sheetnames else workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]

    source_rows = load_swagger_rows(sheet, headers)
    remove_previous_generated(sheet, headers)

    generated_rows: list[dict[str, Any]] = []
    tc_number = START_NUMBER

    for source in source_rows:
        api_name = str(source["API_Name"]).strip()
        request_file = str(source["Request_File"]).strip()
        base_path = REQUEST_DIR / request_file
        base_payload = load_json(base_path)
        primary = pick_primary_field(base_payload)
        if primary is None:
            continue
        alternate = pick_alternate_field(base_payload, primary[0]) or primary
        variants = [
            ("missing", primary, f"missing required field {primary[0]}"),
            ("null", primary, f"null required field {primary[0]}"),
            ("invalid", primary, f"invalid format/value for {primary[0]}"),
            ("boundary", alternate, f"boundary value for {alternate[0]}"),
        ]
        for mutation, (path, value), description_suffix in variants:
            tc_id = f"{TC_PREFIX}{tc_number}"
            output_file = f"{REQUEST_PREFIX}{slugify(api_name)}_{mutation}_{tc_number}.json"
            write_json(REQUEST_DIR / output_file, build_case_payload(base_payload, mutation, path, value))
            row = {header: "" for header in headers}
            row.update(source)
            row.update(
                {
                    "TC_ID": tc_id,
                    "Description": f"Generated acquiring {api_name} negative regression - {description_suffix}",
                    "Bank": "mib",
                    "Request_File": output_file,
                    "Expected_Result": "business error response_code",
                    "Validation_Type": "response",
                    "Execute (Y/N)": "N",
                    "Validation_Rules": json.dumps(
                        {
                            "any_of": [
                                '"response_code": "068"',
                                '"response_code": "400"',
                                '"response_code": "501"',
                                '"response_code": "404"',
                                '"response_code": "120"',
                                '"response_code": "114"',
                                '"response_code": "99"',
                            ]
                        }
                    ),
                    "Test_Type": "negative",
                }
            )
            generated_rows.append(row)
            tc_number += 1

    for row in generated_rows:
        sheet.append([row.get(header, "") for header in headers])

    workbook.save(WORKBOOK_PATH)
    print(f"source_swagger_rows={len(source_rows)}")
    print(f"generated_regression_rows={len(generated_rows)}")
    print(f"total_new_swagger_coverage={len(source_rows) + len(generated_rows)}")


if __name__ == "__main__":
    main()
