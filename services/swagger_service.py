"""Swagger/OpenAPI import helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml
from openpyxl import Workbook, load_workbook

from services.config_service import CONFIG_DIR, ROOT_DIR, load_yaml, write_yaml


@dataclass
class SwaggerImportSummary:
    imported: int = 0
    skipped: int = 0
    modified: int = 0
    errors: list[str] = field(default_factory=list)
    report_file: str = ""


def load_spec_from_url(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def load_spec_from_bytes(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8")
    if not text.strip():
        return {}
    if text.lstrip().startswith("{"):
        return json.loads(text)
    parsed = yaml.safe_load(text)
    return parsed if isinstance(parsed, dict) else {}


def import_openapi_spec(spec: dict[str, Any], service_id: str) -> SwaggerImportSummary:
    summary = SwaggerImportSummary()
    api_path = CONFIG_DIR / "apis.yaml"
    config = load_yaml(api_path)
    service_config = config.setdefault("services", {}).setdefault(service_id, {})
    apis = service_config.setdefault("apis", {})
    requests_dir = ROOT_DIR / "requests" / service_id
    requests_dir.mkdir(parents=True, exist_ok=True)

    for path, path_item in (spec.get("paths", {}) or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            api_name = str(operation.get("operationId") or _name_from_path(method, path))
            if _looks_like_auth_api(api_name, path):
                auth_config = service_config.setdefault("auth", {"apis": [], "token_json_path": "token"})
                auth_apis = auth_config.setdefault("apis", [])
                if api_name not in auth_apis:
                    auth_apis.append(api_name)
            if api_name in apis:
                template_file = requests_dir / f"{api_name}.json"
                generated_template = _sample_body(spec, operation)
                if _should_refresh_template(template_file, generated_template):
                    template_file.write_text(
                        json.dumps(generated_template, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    summary.modified += 1
                else:
                    summary.skipped += 1
                continue
            apis[api_name] = {
                "endpoint": path,
                "method": method.upper(),
                "headers": {"Content-Type": "application/json"},
            }
            if not _looks_like_auth_api(api_name, path):
                service_config.setdefault("token_routing", {}).setdefault(api_name, "default")
            template_file = requests_dir / f"{api_name}.json"
            if not template_file.exists():
                template_file.write_text(
                    json.dumps(_sample_body(spec, operation), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            _append_testcase_row(service_id, api_name, template_file.name)
            summary.imported += 1

    write_yaml(api_path, config)
    report_path = ROOT_DIR / "results" / "swagger_import_report.json"
    summary.report_file = str(report_path)
    report_path.write_text(json.dumps(summary.__dict__, indent=2), encoding="utf-8")
    return summary


def _name_from_path(method: str, path: str) -> str:
    cleaned = path.strip("/").replace("{", "").replace("}", "")
    cleaned = cleaned.replace("/", "_").replace("-", "_")
    return f"{method.lower()}_{cleaned}" if cleaned else method.lower()


def _looks_like_auth_api(api_name: str, path: str) -> bool:
    text = f"{api_name} {path}".lower()
    return any(token in text for token in ["authenticate", "authentication", "token", "login"])


def _should_refresh_template(template_file: Path, generated_template: Any) -> bool:
    if not template_file.exists():
        return bool(generated_template)
    try:
        current = json.loads(template_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return current in ({}, [], None) and generated_template not in ({}, [], None)


def _sample_body(spec: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    request_body = operation.get("requestBody", {})
    content = request_body.get("content", {}) if isinstance(request_body, dict) else {}
    media = content.get("application/json") or content.get("*/*") or next(iter(content.values()), {})
    schema = media.get("schema", {}) if isinstance(media, dict) else {}
    example = _extract_media_example(media)
    if example not in ({}, [], None):
        return _enrich_sample_defaults(example)
    if not schema:
        for parameter in operation.get("parameters", []) or []:
            if isinstance(parameter, dict) and parameter.get("in") == "body":
                schema = parameter.get("schema", {})
                if "example" in parameter:
                    return parameter["example"]
                break
    return _enrich_sample_defaults(_sample_from_schema(spec, schema))


def _extract_media_example(media: dict[str, Any]) -> Any:
    if not isinstance(media, dict):
        return {}
    if "example" in media:
        return media["example"]
    examples = media.get("examples", {})
    if isinstance(examples, dict):
        for item in examples.values():
            if isinstance(item, dict) and "value" in item:
                return item["value"]
    return {}


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        return {}
    current: Any = spec
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(current, dict):
            return {}
        current = current.get(part.replace("~1", "/").replace("~0", "~"))
    return current if isinstance(current, dict) else {}


def _sample_from_schema(spec: dict[str, Any], schema: dict[str, Any], depth: int = 0) -> Any:
    if not isinstance(schema, dict):
        return {}
    if depth > 8:
        return {}
    if "$ref" in schema:
        return _sample_from_schema(spec, _resolve_ref(spec, str(schema["$ref"])), depth + 1)
    if "allOf" in schema:
        merged: dict[str, Any] = {}
        for item in schema.get("allOf", []):
            sample = _sample_from_schema(spec, item, depth + 1)
            if isinstance(sample, dict):
                merged.update(sample)
        return merged
    for combiner in ["oneOf", "anyOf"]:
        if combiner in schema and schema[combiner]:
            return _sample_from_schema(spec, schema[combiner][0], depth + 1)
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if schema.get("type") == "array":
        return [_sample_from_schema(spec, schema.get("items", {}), depth + 1)]
    properties = schema.get("properties", {})
    if properties:
        return {key: _sample_from_schema(spec, value, depth + 1) for key, value in properties.items()}
    if schema.get("type") == "string":
        return _string_placeholder(schema)
    if schema.get("type") in {"integer", "number"}:
        return 0
    if schema.get("type") == "boolean":
        return False
    return {}


def _string_placeholder(schema: dict[str, Any]) -> str:
    fmt = str(schema.get("format", "")).lower()
    if fmt == "date":
        return "${DATE}"
    if fmt in {"date-time", "datetime"}:
        return "${LOCAL_DATETIME}"
    if fmt == "uuid":
        return "${RTP_ID_UNIQUE}"
    return ""


def _enrich_sample_defaults(payload: Any, parent_key: str = "") -> Any:
    """Replace empty Swagger placeholders with safe, reusable test defaults."""
    if isinstance(payload, dict):
        return {key: _enrich_sample_defaults(value, key) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_enrich_sample_defaults(item, parent_key) for item in payload]
    if payload not in ("", 0):
        return payload

    key = parent_key.lower()
    if "datetime" in key or key.endswith("dateTime".lower()):
        return "${LOCAL_DATETIME}"
    if key.endswith("date") or "relateddate" in key:
        return "${DATE}"
    if key == "rrn":
        return "${RRN}"
    if key == "stan":
        return "${STAN}"
    if key == "currency":
        return "PKR"
    if key == "country":
        return "PK"
    if key in {"iban", "sender_iban"}:
        return "PK14MCIB0481000001240001"
    if key == "receiver_iban":
        return "PK61ABPA0010000019474073"
    if key == "memberid":
        return "MCIB01"
    if "merchantname" in key or key == "dbaname":
        return "Test Merchant"
    if "payername" in key or "sendername" in key:
        return "MOHAMMAD FAYYAZ"
    if "payeename" in key or "receivername" in key:
        return "Imran"
    if "referenceid" in key or key.endswith("messageid"):
        return "REF${RRN}"
    if "reason" in key:
        return "DUPLICATE"
    if key in {"mcc", "merchantcategorycode"}:
        return "5812"
    if "purpose" in key:
        return "027"
    if "amount" in key and payload == 0:
        return 110
    return payload


def _append_testcase_row(service_id: str, api_name: str, request_file: str) -> None:
    source_map = {
        "cas": ("sit_testcases.xlsx", "SIT"),
        "acquiring": ("sit_testcases_acquiring.xlsx", "ACQUIRING"),
        "merchant_cas": ("sit_testcases_merchant_cas.xlsx", "MERCHANT_CAS"),
    }
    file_name, sheet_name = source_map.get(
        service_id,
        (f"sit_testcases_{service_id}.xlsx", service_id.upper()),
    )
    workbook_path = ROOT_DIR / "testcases" / file_name
    if not workbook_path.exists():
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = sheet_name
        sheet.append(
            [
                "TC_ID",
                "Service",
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
        )
        workbook.save(workbook_path)

    workbook = load_workbook(workbook_path)
    sheet = workbook[sheet_name] if sheet_name in workbook.sheetnames else workbook.active
    headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
    if api_name in {str(row[headers.index("API_Name")] or "") for row in sheet.iter_rows(min_row=2, values_only=True) if "API_Name" in headers}:
        return
    row = {header: "" for header in headers}
    row.update(
        {
            "TC_ID": f"TC_SWAGGER_{sheet.max_row}",
            "Description": f"Generated smoke testcase for {api_name}",
            "Bank": "mib" if service_id == "acquiring" else "bank1",
            "API_Name": api_name,
            "Request_File": request_file,
            "Expected_Result": "success",
            "Validation_Type": "response",
            "Execute (Y/N)": "N",
            "Test_Type": "positive",
        }
    )
    sheet.append([row.get(header, "") for header in headers])
    workbook.save(workbook_path)
