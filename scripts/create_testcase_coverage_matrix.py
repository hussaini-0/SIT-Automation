from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "testcase_coverage_matrix_current.csv"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.testcase_service import load_testcase_inventory


def target_counts(api_name: str) -> dict[str, int]:
    api_key = api_name.strip().lower()
    base = {
        "target_positive": 2,
        "target_negative": 6,
        "target_boundary": 2,
        "target_auth": 1,
        "target_duplicate": 1,
        "target_flow": 0,
    }

    if api_key == "authenticate":
        base.update(
            {
                "target_positive": 2,
                "target_negative": 4,
                "target_boundary": 1,
                "target_auth": 2,
                "target_duplicate": 0,
                "target_flow": 0,
            }
        )
    elif "status" in api_key or "inquiry" in api_key:
        base["target_flow"] = 1
    elif "payment" in api_key or "directposting" in api_key or "transaction" in api_key:
        base["target_flow"] = 1

    return base


def priority_for_gap(gap_total: int, api_name: str) -> str:
    api_key = api_name.strip().lower()
    if api_key == "authenticate":
        return "P0"
    if "payment" in api_key or "directposting" in api_key or "transaction" in api_key:
        return "P0" if gap_total > 0 else "P1"
    if gap_total >= 8:
        return "P1"
    return "P2"


def main() -> None:
    records = load_testcase_inventory()
    grouped: dict[tuple[str, str], dict[str, int]] = {}

    for record in records:
        key = (record.service, record.api_name)
        bucket = grouped.setdefault(
            key,
            {
                "current_total": 0,
                "current_positive": 0,
                "current_negative": 0,
                "current_other": 0,
            },
        )
        bucket["current_total"] += 1
        if record.test_type == "positive":
            bucket["current_positive"] += 1
        elif record.test_type == "negative":
            bucket["current_negative"] += 1
        else:
            bucket["current_other"] += 1

    rows: list[dict[str, object]] = []
    for (service, api_name), counts in sorted(grouped.items()):
        targets = target_counts(api_name)
        target_total = sum(targets.values())
        gap_total = max(0, target_total - int(counts["current_total"]))
        rows.append(
            {
                "service": service,
                "api_name": api_name,
                **counts,
                **targets,
                "target_total": target_total,
                "gap_total": gap_total,
                "priority": priority_for_gap(gap_total, api_name),
                "notes": "",
            }
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "service",
        "api_name",
        "current_total",
        "current_positive",
        "current_negative",
        "current_other",
        "target_positive",
        "target_negative",
        "target_boundary",
        "target_auth",
        "target_duplicate",
        "target_flow",
        "target_total",
        "gap_total",
        "priority",
        "notes",
    ]
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote coverage matrix: {OUTPUT}")
    print(f"APIs covered: {len(rows)}")


if __name__ == "__main__":
    main()
