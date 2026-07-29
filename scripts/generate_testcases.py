from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openpyxl import Workbook, load_workbook


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


STANDARD_HEADERS = [
    "TC_ID",
    "Description",
    "Bank",
    "API_Name",
    "Request_File",
    "Expected_Result",
    "Validation_Type",
    "Execute (Y/N)",
    "Flow_Config",
    "Validation_Rules",
    "Test_Type",
    "Trx_type",
]


@dataclass
class GeneratedCase:
    testcase_id: str
    description: str
    request_file: str
    payload: dict[str, Any]
    row: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate positive and negative testcase variants.")
    parser.add_argument(
        "--spec",
        default=str(ROOT / "config" / "testcase_generation.yaml"),
        help="YAML spec file describing suites and testcase variants.",
    )
    parser.add_argument(
        "--output-root",
        default=str(ROOT / "generated_testcases"),
        help="Directory where generated requests and preview workbooks will be written.",
    )
    parser.add_argument(
        "--append-workbook",
        action="store_true",
        help="Append generated rows to the suite workbook instead of creating preview workbooks.",
    )
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def reset_suite_outputs(output_request_dir: Path, request_prefix: str, output_workbook: Path) -> None:
    if output_request_dir.exists():
        for path in output_request_dir.glob(f"{request_prefix}_*.json"):
            path.unlink()
    if output_workbook.exists():
        output_workbook.unlink()


def parse_start_id(value: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Za-z_]+)(\d+)", value.strip())
    if not match:
        raise ValueError(f"Invalid start_id '{value}'. Use a prefix like TC900.")
    return match.group(1), int(match.group(2))


def path_token(part: str) -> int | str:
    return int(part) if part.isdigit() else part


def test_data_value(test_data_key: str, test_data: dict[str, Any]) -> Any:
    key = str(test_data_key).strip()
    if not key:
        raise ValueError("test_data key cannot be empty.")
    if key not in test_data:
        raise ValueError(f"Unknown test_data key '{key}' in config/test_data.yaml")
    return test_data[key]


def placeholder_for_test_data(test_data_key: str, test_data: dict[str, Any]) -> str:
    value = test_data_value(test_data_key, test_data)
    key = str(test_data_key).strip()
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        return value
    return f"${{{key.upper()}}}"


def resolve_mutation_value(value: Any, test_data: dict[str, Any]) -> Any:
    if isinstance(value, dict) and "from_test_data" in value:
        mode = str(value.get("mode", "placeholder")).strip().lower()
        key = str(value["from_test_data"])
        return test_data_value(key, test_data) if mode == "value" else placeholder_for_test_data(key, test_data)
    return value


def set_path_value(payload: dict[str, Any], path: str, value: Any) -> None:
    tokens = [path_token(part) for part in path.split(".")]
    current: Any = payload

    for index, token in enumerate(tokens[:-1]):
        next_token = tokens[index + 1]
        if isinstance(token, int):
            if not isinstance(current, list):
                raise ValueError(f"Cannot traverse list index in path '{path}'.")
            while len(current) <= token:
                current.append({} if isinstance(next_token, str) else [])
            if not isinstance(current[token], (dict, list)):
                current[token] = {} if isinstance(next_token, str) else []
            current = current[token]
            continue

        if not isinstance(current, dict):
            raise ValueError(f"Cannot traverse path '{path}' because '{token}' is not an object.")
        if token not in current or not isinstance(current[token], (dict, list)):
            current[token] = {} if isinstance(next_token, str) else []
        current = current[token]

    final_token = tokens[-1]
    if isinstance(final_token, int):
        if not isinstance(current, list):
            raise ValueError(f"Cannot set list index in path '{path}'.")
        while len(current) <= final_token:
            current.append(None)
        current[final_token] = value
    else:
        if not isinstance(current, dict):
            raise ValueError(f"Cannot set path '{path}'.")
        current[final_token] = value


def path_exists(payload: Any, path: str) -> bool:
    current = payload
    for part in path.split("."):
        token = path_token(part)
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                return False
            current = current[token]
            continue
        if not isinstance(current, dict) or token not in current:
            return False
        current = current[token]
    return True


def remove_path_value(payload: dict[str, Any], path: str) -> None:
    parts = [path_token(part) for part in path.split(".")]
    current: Any = payload
    for part in parts[:-1]:
        if isinstance(part, int):
            if not isinstance(current, list) or part >= len(current):
                return
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                return
            current = current[part]
    final_part = parts[-1]
    if isinstance(final_part, int):
        if isinstance(current, list) and final_part < len(current):
            current.pop(final_part)
    elif isinstance(current, dict):
        current.pop(final_part, None)


def apply_test_data_bindings(
    payload: dict[str, Any],
    bindings: dict[str, Any],
    test_data: dict[str, Any],
    mode: str = "placeholder",
) -> dict[str, Any]:
    updated = copy.deepcopy(payload)
    for path, test_data_key in bindings.items():
        if isinstance(test_data_key, dict):
            key = str(test_data_key.get("key", "")).strip()
            binding_mode = str(test_data_key.get("mode", mode)).strip().lower()
        else:
            key = str(test_data_key).strip()
            binding_mode = mode
        value = test_data_value(key, test_data) if binding_mode == "value" else placeholder_for_test_data(key, test_data)
        set_path_value(updated, str(path).strip(), value)
    return updated


def apply_mutations(payload: dict[str, Any], mutations: list[dict[str, Any]], test_data: dict[str, Any]) -> dict[str, Any]:
    updated: Any = copy.deepcopy(payload)
    for mutation in mutations:
        op = str(mutation.get("op", "set")).strip().lower()
        path = str(mutation.get("path", "")).strip()
        if op == "replace_root":
            updated = resolve_mutation_value(mutation.get("value"), test_data)
            continue
        if not path:
            raise ValueError(f"Mutation is missing a path: {mutation}")
        if op == "set":
            set_path_value(updated, path, resolve_mutation_value(mutation.get("value"), test_data))
        elif op == "remove":
            remove_path_value(updated, path)
        else:
            raise ValueError(f"Unsupported mutation op '{op}'.")
    return updated


def workbook_headers(path: Path, sheet_name: str) -> list[str]:
    if not path.exists():
        return STANDARD_HEADERS
    workbook = load_workbook(path, data_only=True)
    sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    return headers or STANDARD_HEADERS


def append_rows(path: Path, sheet_name: str, headers: list[str], rows: list[dict[str, Any]]) -> None:
    if path.exists():
        workbook = load_workbook(path)
        sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_name
        sheet.append(headers)

    tc_id_index = headers.index("TC_ID") + 1 if "TC_ID" in headers else 1
    incoming_tc_ids = {str(row.get("TC_ID", "")).strip() for row in rows if str(row.get("TC_ID", "")).strip()}
    for row_number in range(sheet.max_row, 1, -1):
        tc_id = str(sheet.cell(row=row_number, column=tc_id_index).value or "").strip()
        if tc_id in incoming_tc_ids:
            sheet.delete_rows(row_number, 1)

    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def generate_suite(suite: dict[str, Any], output_root: Path) -> tuple[list[GeneratedCase], Path, Path]:
    service = str(suite["service"]).strip()
    api_name = str(suite["api_name"]).strip()
    api_label = str(suite.get("api_label", api_name)).strip()
    bank = str(suite.get("bank", "bank1")).strip()
    base_request_file = str(suite["base_request_file"]).strip()
    expected_result = str(suite.get("expected_result", "") or "")
    validation_type = str(suite.get("validation_type", "response")).strip()
    validation_rules = suite.get("validation_rules", {})
    flow_config = str(suite.get("flow_config", "") or "")
    execute_flag = str(suite.get("execute_flag", "Y")).strip().upper() or "Y"
    trx_type = str(suite.get("trx_type", "non-financial")).strip() or "non-financial"
    workbook_path = ROOT / str(suite.get("workbook", f"testcases/sit_testcases_{service}.xlsx"))
    sheet_name = str(suite.get("sheet", service.upper())).strip()
    request_dir = ROOT / "requests" / service
    base_template = load_json(request_dir / base_request_file)
    test_data = load_yaml(ROOT / "config" / "test_data.yaml")
    suite_bindings = suite.get("test_data_bindings", {}) or {}
    binding_mode = str(suite.get("test_data_binding_mode", "placeholder")).strip().lower()
    base_template = apply_test_data_bindings(base_template, suite_bindings, test_data, mode=binding_mode)
    output_request_dir = output_root / "requests" / service
    output_workbook = output_root / "workbooks" / f"{service}_{api_name}_generated.xlsx"
    tc_prefix, start_num = parse_start_id(str(suite.get("start_id", "TC900")))
    request_prefix = str(
        suite.get(
            "request_prefix",
            f"{tc_prefix.lower()}_{re.sub(r'[^a-z0-9]+', '_', api_name.lower()).strip('_')}",
        )
    ).strip()
    reset_suite_outputs(output_request_dir, request_prefix, output_workbook)

    variants = suite.get("variants", [])
    generated: list[GeneratedCase] = []
    counter = start_num

    for variant in variants:
        name = str(variant.get("name", f"{api_name}-{counter}")).strip()
        description_template = str(variant.get("description", name)).strip()
        description = description_template.format(api_label=api_label, api_name=api_name)
        test_type = str(variant.get("test_type", "positive")).strip().lower() or "positive"
        file_stub = str(variant.get("file_stub", name.lower().replace(" ", "_"))).strip()
        mutations = variant.get("mutations", []) or []
        variant_bindings = variant.get("test_data_bindings", {}) or {}
        payload = apply_test_data_bindings(
            base_template,
            variant_bindings,
            test_data,
            mode=str(variant.get("test_data_binding_mode", binding_mode)).strip().lower(),
        )
        extra_paths = [
            str(mutation.get("path", "")).strip()
            for mutation in mutations
            if str(mutation.get("op", "set")).strip().lower() == "set"
            and str(mutation.get("path", "")).strip()
            and not path_exists(payload, str(mutation.get("path", "")).strip())
        ]
        if extra_paths and not bool(variant.get("allow_extra_fields", suite.get("allow_extra_fields", False))):
            print(
                f"  skipped {tc_prefix}{counter:03d} ({name}) because it adds unsupported field(s): "
                f"{', '.join(extra_paths)}"
            )
            counter += 1
            continue
        payload = apply_mutations(payload, mutations, test_data)

        testcase_id = f"{tc_prefix}{counter:03d}"
        request_file = variant.get("request_file") or f"{request_prefix}_{file_stub}.json"
        row = {
            "TC_ID": testcase_id,
            "Service": service,
            "Description": description,
            "Bank": bank,
            "API_Name": str(variant.get("api_name", api_name)).strip(),
            "Request_File": request_file,
            "Expected_Result": str(variant.get("expected_result", expected_result) or ""),
            "Validation_Type": str(variant.get("validation_type", validation_type)).strip(),
            "Execute (Y/N)": str(variant.get("execute_flag", execute_flag)).strip().upper() or "Y",
            "Flow_Config": str(variant.get("flow_config", flow_config) or ""),
            "Validation_Rules": json.dumps(
                variant.get("validation_rules", validation_rules) or {},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if variant.get("validation_rules", validation_rules)
            else "",
            "Test_Type": test_type,
            "Trx_type": str(variant.get("trx_type", trx_type)).strip() or trx_type,
        }
        generated.append(
            GeneratedCase(
                testcase_id=testcase_id,
                description=description,
                request_file=request_file,
                payload=payload,
                row=row,
            )
        )
        counter += 1

    for case in generated:
        write_json(output_request_dir / case.request_file, case.payload)

    headers = workbook_headers(workbook_path, sheet_name)
    append_rows(output_workbook, sheet_name, headers, [case.row for case in generated])
    return generated, output_workbook, workbook_path


def append_suite_to_existing(suite: dict[str, Any], generated: list[GeneratedCase], workbook_path: Path) -> None:
    service = str(suite["service"]).strip()
    sheet_name = str(suite.get("sheet", str(suite["service"]).upper())).strip()
    headers = workbook_headers(workbook_path, sheet_name)
    live_request_dir = ROOT / "requests" / service
    for case in generated:
        write_json(live_request_dir / case.request_file, case.payload)
    append_rows(workbook_path, sheet_name, headers, [case.row for case in generated])


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec).resolve()
    output_root = Path(args.output_root).resolve()
    spec = load_yaml(spec_path)
    suites = spec.get("suites", [])
    if not suites:
        raise ValueError(f"No suites found in {spec_path}")

    print(f"Using spec: {spec_path}")
    print(f"Writing generated assets to: {output_root}")
    total_cases = 0

    for suite in suites:
        generated, preview_workbook, workbook_path = generate_suite(suite, output_root)
        total_cases += len(generated)
        print(
            f"- {suite['service']} / {suite['api_name']}: generated {len(generated)} testcase(s) "
            f"into {preview_workbook}"
        )
        if args.append_workbook:
            append_suite_to_existing(suite, generated, workbook_path)
            print(f"  appended rows to {workbook_path}")

    print(f"Total generated testcases: {total_cases}")


if __name__ == "__main__":
    main()
