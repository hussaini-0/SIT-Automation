"""Testcase inventory helpers for Excel-backed SIT workbooks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

from openpyxl import load_workbook

from services.config_service import ROOT_DIR, get_banks_config, get_services_config
from testcase_models import ServiceTestCase


@dataclass(frozen=True)
class TestcaseRecord:
    tc_id: str
    service: str
    service_name: str
    api_name: str
    module: str
    description: str
    request_file: str
    expected_result: str
    validation_type: str
    execute: str
    bank: str
    flow_config: str = ""
    validation_rules: str = ""
    test_type: str = "positive"
    trx_type: str = "non-financial"


_CaseT = TypeVar("_CaseT", TestcaseRecord, ServiceTestCase)


def scope_run_cases(
    cases: list[_CaseT],
    *,
    skip_rtp: bool = False,
    register_customer_limit: int | None = None,
) -> list[_CaseT]:
    """Apply optional run-only API limits without changing the workbook inventory."""
    selected = [case for case in cases if not (skip_rtp and "rtp" in case.api_name.lower())]
    if register_customer_limit is None:
        return selected

    limit = max(0, register_customer_limit)
    groups: dict[tuple[str, str], list[tuple[int, _CaseT]]] = {}
    for index, case in enumerate(selected):
        if case.service == "cas" and case.api_name.lower() == "registercustomer":
            groups.setdefault((case.service, case.bank.lower()), []).append((index, case))

    excluded_indices: set[int] = set()
    for group in groups.values():
        preferred = [
            item for tc_id in ("TC243", "TC249")
            for item in group if item[1].tc_id.upper() == tc_id
        ]
        ordered = preferred + [item for item in group if item not in preferred]
        kept_indices = {index for index, _ in ordered[:limit]}
        excluded_indices.update(index for index, _ in group if index not in kept_indices)

    return [case for index, case in enumerate(selected) if index not in excluded_indices]


def _cell(row: tuple[Any, ...], headers: dict[str, int], name: str, default: str = "") -> str:
    index = headers.get(name)
    if index is None or index >= len(row):
        return default
    value = row[index]
    return str(value if value is not None else default).strip()


def _module_for_api(api_name: str, endpoint: str) -> str:
    path = endpoint.strip("/")
    if path:
        parts = [part for part in path.split("/") if part and not part.startswith("{")]
        if len(parts) >= 2:
            return parts[-2].replace("-", " ").replace("_", " ").title()
    return api_name.split("_")[0].replace("-", " ").title() or "General"


def _shared_testcase_sources(services: dict[str, Any]) -> list[dict[str, Any]]:
    testcase_sources: list[dict[str, Any]] = [
        {"service": "cas", "file": ROOT_DIR / "testcases" / "sit_testcases.xlsx", "sheet": "SIT"},
        {"service": "acquiring", "file": ROOT_DIR / "testcases" / "sit_testcases_acquiring.xlsx", "sheet": "ACQUIRING"},
        {
            "service": "merchant_cas",
            "file": ROOT_DIR / "testcases" / "sit_testcases_merchant_cas.xlsx",
            "sheet": "MERCHANT_CAS",
        },
    ]
    configured_static_services = {str(source["service"]) for source in testcase_sources}
    for service_id in sorted(set(services) - configured_static_services):
        workbook_path = ROOT_DIR / "testcases" / f"sit_testcases_{service_id}.xlsx"
        if workbook_path.exists():
            testcase_sources.append(
                {"service": service_id, "file": workbook_path, "sheet": service_id.upper()}
            )
    return testcase_sources


def _bank_specific_testcase_sources(bank_names: list[str], services: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for bank_name in bank_names:
        workbook_path = ROOT_DIR / "testcases" / f"sit_testcases_{bank_name.lower()}.xlsx"
        if not workbook_path.exists():
            continue
        for source in _shared_testcase_sources(services):
            sources.append(
                {
                    "service": source["service"],
                    "file": workbook_path,
                    "sheet": source["sheet"],
                    "bank": bank_name,
                    "strict_sheet": True,
                }
            )
    return sources


def _normalized_bank_names(banks: list[str] | None) -> list[str]:
    configured_banks = get_banks_config()
    configured_by_lower = {str(key).lower(): str(key) for key in configured_banks}
    normalized: list[str] = []
    for bank in banks or []:
        bank_key = str(bank or "").strip()
        if not bank_key:
            continue
        normalized.append(configured_by_lower.get(bank_key.lower(), bank_key))
    return normalized


def load_testcase_inventory(*, banks: list[str] | None = None) -> list[TestcaseRecord]:
    services = get_services_config()
    requested_banks = _normalized_bank_names(banks)
    testcase_sources = (
        _bank_specific_testcase_sources(requested_banks, services)
        if requested_banks
        else _shared_testcase_sources(services)
    )
    if requested_banks and not testcase_sources:
        testcase_sources = [
            {**source, "bank": bank_name}
            for bank_name in requested_banks
            for source in _shared_testcase_sources(services)
        ]
    records: list[TestcaseRecord] = []

    for source in testcase_sources:
        source_service = str(source["service"])
        source_file = Path(source["file"])
        if not source_file.exists() or source_file.name.startswith("~$"):
            continue

        workbook = load_workbook(source_file, data_only=True)
        sheet_name = str(source["sheet"])
        if sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
        elif source.get("strict_sheet"):
            continue
        else:
            sheet = workbook.active
        headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
        header_index = {header: idx for idx, header in enumerate(headers)}

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue

            service = _resolve_service(row, header_index, source_service, services).lower()
            api_name = _cell(row, header_index, "API_Name")
            flow_config = _cell(row, header_index, "Flow_Config")
            explicit_trx_type = _cell(row, header_index, "Trx_type")
            api_def = services.get(service, {}).get("apis", {}).get(api_name, {})
            records.append(
                TestcaseRecord(
                    tc_id=_cell(row, header_index, "TC_ID"),
                    service=service,
                    service_name=str(services.get(service, {}).get("display_name", service)),
                    api_name=api_name,
                    module=_module_for_api(api_name, str(api_def.get("endpoint", ""))),
                    description=_cell(row, header_index, "Description"),
                    request_file=_cell(row, header_index, "Request_File"),
                    expected_result=_cell(row, header_index, "Expected_Result"),
                    validation_type=_cell(row, header_index, "Validation_Type", "response"),
                    execute=_cell(row, header_index, "Execute (Y/N)", "N").upper(),
                    bank=str(source.get("bank") or _cell(row, header_index, "Bank")),
                    flow_config=flow_config,
                    validation_rules=_cell(row, header_index, "Validation_Rules"),
                    test_type=_cell(row, header_index, "Test_Type", "positive").lower(),
                    trx_type=_resolve_trx_type(service, api_name, flow_config, explicit_trx_type, services),
                )
            )

    return records


def filter_testcase_inventory(
    records: list[TestcaseRecord],
    *,
    services: list[str] | None = None,
    apis: list[str] | None = None,
    testcase_ids: list[str] | None = None,
    banks: list[str] | None = None,
    include_disabled: bool = False,
) -> list[TestcaseRecord]:
    service_filter = {service.strip().lower() for service in services or [] if service and service.strip()}
    api_filter = {api.strip() for api in apis or [] if api and api.strip()}
    testcase_filter = {tc_id.strip() for tc_id in testcase_ids or [] if tc_id and tc_id.strip()}
    bank_filter = {bank.strip().lower() for bank in banks or [] if bank and bank.strip()}

    selected = records
    if service_filter:
        selected = [record for record in selected if record.service in service_filter]
    if not include_disabled:
        selected = [record for record in selected if record.execute == "Y"]
    if api_filter:
        selected = [record for record in selected if record.api_name in api_filter]
    if testcase_filter:
        selected = [record for record in selected if record.tc_id in testcase_filter]
    if bank_filter:
        selected = [record for record in selected if record.bank.strip().lower() in bank_filter]
    return selected


def select_testcase_inventory(
    *,
    services: list[str] | None = None,
    apis: list[str] | None = None,
    testcase_ids: list[str] | None = None,
    banks: list[str] | None = None,
    include_disabled: bool = False,
) -> list[TestcaseRecord]:
    return filter_testcase_inventory(
        load_testcase_inventory(banks=banks),
        services=services,
        apis=apis,
        testcase_ids=testcase_ids,
        banks=banks,
        include_disabled=include_disabled,
    )


def _resolve_service(
    row: tuple[Any, ...],
    header_index: dict[str, int],
    default_service: str,
    services: dict[str, Any],
) -> str:
    service_value = _cell(row, header_index, "Service").lower()
    if service_value:
        return service_value

    request_file = _cell(row, header_index, "Request_File").lower()
    api_name = _cell(row, header_index, "API_Name")
    for token, service_id in [
        ("acq", "acquiring"),
        ("acquiring", "acquiring"),
        ("mcas", "merchant_cas"),
        ("merchant_cas", "merchant_cas"),
    ]:
        if token in request_file:
            return service_id

    matches = [
        service_id
        for service_id, config in services.items()
        if api_name and api_name in (config.get("apis", {}) or {})
    ]
    return matches[0] if len(matches) == 1 else default_service


def _resolve_trx_type(
    service: str,
    api_name: str,
    flow_config: str,
    explicit_trx_type: str,
    services: dict[str, Any],
) -> str:
    normalized = explicit_trx_type.strip().lower().replace("_", "-")
    if normalized:
        return normalized

    service_id = service.strip().lower()
    api_names = {api_name.strip().lower()}
    flow = (services.get(service_id, {}).get("flows", {}) or {}).get(flow_config, {})
    if flow:
        api_names.add(str(flow.get("initial_api", "")).strip().lower())
        api_names.add(str((flow.get("polling") or {}).get("api", "")).strip().lower())
        api_names.add(str((flow.get("on_success") or {}).get("next_api", "")).strip().lower())

    if service_id == "merchant_cas":
        return "non-financial" if api_name == "authenticate" else "financial"
    if service_id == "cas" and any("payment" in name or "directposting" in name for name in api_names):
        return "financial"
    return "non-financial"


def to_runner_testcase(record: TestcaseRecord) -> ServiceTestCase:
    payload = asdict(record)
    for key in ["service_name", "module"]:
        payload.pop(key, None)
    return ServiceTestCase(**payload)


def inventory_summary() -> dict[str, int]:
    records = load_testcase_inventory()
    return {
        "services": len({record.service for record in records}),
        "apis": len({(record.service, record.api_name) for record in records if record.api_name}),
        "testcases": len(records),
    }
