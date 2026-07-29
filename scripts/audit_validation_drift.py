from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
REQUESTS_DIR = ROOT / "requests"
TESTCASES_DIR = ROOT / "testcases"

STALE_EXPECTATION_HINTS = {
    "Minimum amount allowed: 0": "API may now return the newer titlefetch decimal-format parse error.",
    "Invalid gender": "Prefer the full API wording or a stable substring/validation rule.",
    "JSON parse error: Amount must be a decimal up to 2 decimal places (e.g. 0.0, 10.50). Integer OR Other values like 0, 10 or ABC are not allowed.": "API wording may now use 'amount must be a decimal value'.",
}


def find_integer_amounts(node: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            if key in {"amount", "fee"} and isinstance(value, int):
                findings.append(f"{child_path}={value}")
            findings.extend(find_integer_amounts(value, child_path))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            findings.extend(find_integer_amounts(item, f"{path}[{index}]"))
    return findings


def audit_requests() -> list[str]:
    findings: list[str] = []
    for path in sorted(REQUESTS_DIR.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(f"{path.relative_to(ROOT)} invalid JSON: {exc}")
            continue
        for finding in find_integer_amounts(payload):
            findings.append(f"{path.relative_to(ROOT)} -> integer numeric field {finding}")
    return findings


def audit_workbooks() -> list[str]:
    findings: list[str] = []
    for path in sorted(TESTCASES_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        workbook = load_workbook(path, read_only=True, data_only=True)
        for ws in workbook.worksheets:
            headers = [str(cell.value).strip() if cell.value is not None else "" for cell in ws[1]]
            header_index = {header: idx for idx, header in enumerate(headers)}
            tc_idx = header_index.get("TC_ID")
            expected_idx = header_index.get("Expected_Result")
            if tc_idx is None or expected_idx is None:
                continue
            for row in ws.iter_rows(min_row=2, values_only=True):
                tc_id = str(row[tc_idx]).strip() if row[tc_idx] is not None else ""
                expected = str(row[expected_idx]).strip() if row[expected_idx] is not None else ""
                for snippet, note in STALE_EXPECTATION_HINTS.items():
                    if expected.strip().lower() == snippet.strip().lower():
                        findings.append(
                            f"{path.relative_to(ROOT)} [{ws.title}] {tc_id}: stale expectation '{expected}' -> {note}"
                        )
    return findings


def main() -> None:
    findings = [*audit_requests(), *audit_workbooks()]
    if not findings:
        print("No validation drift findings detected.")
        return
    print("Validation drift findings:")
    for finding in findings:
        print(f"- {finding}")


if __name__ == "__main__":
    main()
