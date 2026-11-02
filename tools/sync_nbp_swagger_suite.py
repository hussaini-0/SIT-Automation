"""Prepare NBP-only Merchant CAS requests and audit the three NBP Swagger specs."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import yaml
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "nbp-swagger-20260916"
WORKBOOK = ROOT / "testcases" / "sit_testcases_nbp.xlsx"
SPECS = {
    "SIT": ("cas", ROOT / "specs" / "nbp" / "9091.openapi.json"),
    "MERCHANT_CAS": ("merchant_cas", ROOT / "specs" / "nbp" / "9093.openapi.json"),
    "ACQUIRING": ("acquiring", ROOT / "specs" / "nbp" / "9096.openapi.json"),
}
NBP_REQUEST_APIS = {
    "merchant_payment_alias",
    "merchant_payment_direct_rtpn",
    "merchant_payment_direct_rtpl",
}
EXCLUDED_PATHS = {"/api/v1/paysyslabs/customers/registercaa"}


def load_specs() -> dict[str, dict]:
    return {sheet: json.loads(path.read_text(encoding="utf-8")) for sheet, (_, path) in SPECS.items()}


def iter_cases(workbook):
    for sheet_name in SPECS:
        sheet = workbook[sheet_name]
        rows = sheet.iter_rows(values_only=True)
        headers = {name: index for index, name in enumerate(next(rows)) if name}
        for row_number, row in enumerate(rows, start=2):
            if not row[0]:
                continue
            yield sheet_name, row_number, headers, row


def schema_for(spec: dict, endpoint: str, method: str) -> dict | None:
    path = "/" + endpoint.split("?", 1)[0].lstrip("/")
    operation = spec.get("paths", {}).get(path, {}).get(method.lower())
    if operation is None:
        return None
    return operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})


def dereference(spec: dict, schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref:
        return spec["components"]["schemas"][ref.rsplit("/", 1)[-1]]
    return schema


def prune_to_schema(value, schema: dict, spec: dict):
    schema = dereference(spec, schema)
    if isinstance(value, dict) and "properties" in schema:
        properties = schema["properties"]
        return {
            key: prune_to_schema(item, properties[key], spec)
            for key, item in value.items()
            if key in properties
        }
    if isinstance(value, list) and "items" in schema:
        return [prune_to_schema(item, schema["items"], spec) for item in value]
    return value


def schema_issues(value, schema: dict, spec: dict, path: str = "") -> list[str]:
    schema = dereference(spec, schema)
    issues: list[str] = []
    if isinstance(value, dict) and "properties" in schema:
        properties = schema["properties"]
        for key in schema.get("required", []):
            if key not in value:
                issues.append(f"missing:{path}{key}")
            elif value[key] in (None, ""):
                issues.append(f"blank:{path}{key}")
        for key, item in value.items():
            if key not in properties:
                issues.append(f"extra:{path}{key}")
            else:
                issues.extend(schema_issues(item, properties[key], spec, f"{path}{key}."))
    elif isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            issues.extend(schema_issues(item, schema["items"], spec, f"{path}{index}."))
    return issues


def scaffold_value(schema: dict, spec: dict, field: str = ""):
    schema = dereference(spec, schema)
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        return {
            key: scaffold_value(properties[key], spec, key)
            for key in schema.get("required", [])
            if key in properties
        }
    if kind == "array":
        return []
    if kind in {"number", "integer"}:
        return 0
    if kind == "boolean":
        return False
    if field.lower() == "rrn":
        return "${RRN}"
    if field.lower() == "stan":
        return "${STAN}"
    return ""


def prepare_missing_operations(workbook, specs: dict, api_config: dict) -> list[dict]:
    additions: list[dict] = []
    extra_config: dict = {"services": {}}
    for sheet_name, (service, _) in SPECS.items():
        if service == "acquiring":
            continue
        sheet = workbook[sheet_name]
        rows = sheet.iter_rows(values_only=True)
        headers = {name: index for index, name in enumerate(next(rows)) if name}
        existing_names = {
            str(row[headers["API_Name"]]) for row in rows if row[headers["TC_ID"]]
        }
        existing_routes = {
            ("/" + definition["endpoint"].split("?", 1)[0].lstrip("/"), definition["method"].upper())
            for name, definition in api_config[service]["apis"].items()
            if name in existing_names
        }
        base_routes = {
            ("/" + definition["endpoint"].split("?", 1)[0].lstrip("/"), definition["method"].upper()): name
            for name, definition in api_config[service]["apis"].items()
        }
        extra_apis: dict = {}
        for path, methods in specs[sheet_name]["paths"].items():
            if path in EXCLUDED_PATHS:
                continue
            for method, operation in methods.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                route = (path, method.upper())
                if route in existing_routes:
                    continue
                operation_id = operation.get("operationId") or path.rsplit("/", 1)[-1]
                slug = re.sub(r"[^a-z0-9]+", "_", operation_id.lower()).strip("_")
                api_name = base_routes.get(route) or f"nbp_{operation_id}"
                if route not in base_routes:
                    extra_apis[api_name] = {
                        "endpoint": path,
                        "method": method.upper(),
                        "headers": {"Content-Type": "application/json"},
                    }
                request_name = f"nbp/swagger_{slug}.json"
                schema = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
                body = scaffold_value(schema, specs[sheet_name]) if schema else {}
                for parameter in operation.get("parameters", []):
                    if parameter.get("in") == "path":
                        body.setdefault(parameter["name"], "")
                target = ROOT / "requests" / service / request_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                if api_name not in existing_names:
                    additions.append(
                        {
                            "sheet": sheet_name,
                            "tc_id": f"NBP_SWAGGER_{SPECS[sheet_name][1].stem[:4]}_{slug.upper()}",
                            "description": f"NBP Swagger scaffold for {operation_id}; verified business data needed",
                            "bank": "nbp",
                            "api_name": api_name,
                            "request_file": request_name,
                            "expected_result": "",
                            "validation_type": "response",
                            "execute": "N",
                            "test_type": "positive",
                            "trx_type": "",
                        }
                    )
        if extra_apis:
            extra_config["services"][service] = {"apis": extra_apis}
    (ROOT / "config" / "apis_nbp.yaml").write_text(
        yaml.safe_dump(extra_config, sort_keys=False, allow_unicode=False), encoding="utf-8"
    )
    return additions


def disabled_reason(case_id: str, api: str, description: str, expected: str, body: dict) -> str:
    label = description.lower()
    if "rrn non-numeric" in label and body.get("info", {}).get("rrn") == "${RRN}":
        return "RRN is generated numeric, so this does not test a non-numeric RRN"
    if api == "merchant_payment_alias":
        if any(term in label for term in ("currency invalid", "terminal id missing")):
            return "Target field is absent from PayToAliasRequest"
        if "merchantidalias missing" in label:
            return "merchantIdAlias is optional in PayToAliasRequest"
        if "amount zero" in label and "paymentpurpose" in expected.lower():
            return "Expected purpose error does not match the amount-zero scenario"
    if "duplicate transaction" in expected.lower() and "duplicate" not in label:
        return "Expected duplicate response does not match the testcase target"
    return ""


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    specs = load_specs()
    api_config = yaml.safe_load((ROOT / "config" / "apis.yaml").read_text(encoding="utf-8"))["services"]
    workbook = load_workbook(WORKBOOK, read_only=True, data_only=True)
    workbook_changes: list[dict] = []
    audit: list[dict] = []
    additions = prepare_missing_operations(workbook, specs, api_config)
    nbp_apis = yaml.safe_load((ROOT / "config" / "apis_nbp.yaml").read_text(encoding="utf-8"))["services"]
    for service_id, service_config in nbp_apis.items():
        api_config[service_id]["apis"].update(service_config.get("apis", {}))

    for sheet, row_number, headers, row in iter_cases(workbook):
        service = SPECS[sheet][0]
        api = str(row[headers["API_Name"]] or "")
        case_id = str(row[headers["TC_ID"]] or "")
        request_file = str(row[headers["Request_File"]] or "")
        execute = str(row[headers["Execute (Y/N)"]] or "").upper()
        test_type = str(row[headers["Test_Type"]] or "").lower()
        description = str(row[headers["Description"]] or "")
        expected = str(row[headers["Expected_Result"]] or "")
        definition = api_config[service]["apis"].get(api)
        result = {
            "sheet": sheet,
            "row": row_number,
            "tc_id": case_id,
            "api": api,
            "execute": execute,
            "test_type": test_type,
        }
        if definition is None:
            result["route"] = "unconfigured"
            audit.append(result)
            continue
        schema = schema_for(specs[sheet], definition["endpoint"], definition["method"])
        if schema is None:
            result["route"] = "external_auth" if service == "acquiring" and api == "authenticate" else "not_in_spec"
            audit.append(result)
            continue
        result["route"] = "in_spec"
        if not request_file:
            audit.append(result)
            continue
        source = ROOT / "requests" / service / request_file
        if not source.exists():
            result["request"] = "missing_file"
            audit.append(result)
            continue
        body = json.loads(source.read_text(encoding="utf-8"))

        if sheet == "MERCHANT_CAS" and api in NBP_REQUEST_APIS:
            body = prune_to_schema(body, schema, specs[sheet])
            if api == "merchant_payment_alias":
                body.setdefault("paymentInfo", {})["paymentPurpose"] = "${MERCHANT_ALIAS_PAYMENT_PURPOSE}"
            if "dateTime" in body.get("paymentInfo", {}):
                body["paymentInfo"]["dateTime"] = "${DATETIME}"
            target_name = f"nbp/{Path(request_file).name}"
            target = ROOT / "requests" / service / target_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
            change = {"sheet": sheet, "row": row_number, "request_file": target_name}
            reason = disabled_reason(case_id, api, description, expected, json.loads(source.read_text(encoding="utf-8")))
            if reason:
                change["execute"] = "N"
                result["disabled_reason"] = reason
            workbook_changes.append(change)

        request_schema = dereference(specs[sheet], schema)
        if isinstance(body, dict):
            result["missing_top_required"] = sorted(set(request_schema.get("required", [])) - set(body))
            result["extra_top_fields"] = sorted(set(body) - set(request_schema.get("properties", {})))
            result["schema_issues"] = schema_issues(body, schema, specs[sheet])
        audit.append(result)

    (OUTPUT / "workbook_changes.json").write_text(
        json.dumps(workbook_changes, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "workbook_additions.json").write_text(
        json.dumps(additions, indent=2) + "\n", encoding="utf-8"
    )
    (OUTPUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    counts = Counter((item["sheet"], item["route"]) for item in audit)
    for key, count in sorted(counts.items()):
        print(f"{key[0]} {key[1]}: {count}")
    for sheet in SPECS:
        positives = [item for item in audit if item["sheet"] == sheet and item["test_type"] == "positive" and item["execute"] == "Y"]
        with_issues = [item for item in positives if item.get("schema_issues")]
        print(f"{sheet} enabled positives with schema issues: {len(with_issues)}/{len(positives)}")
    print(f"NBP request files prepared: {len(workbook_changes)}")
    print(f"Cases disabled for mismatched intent: {sum('execute' in item for item in workbook_changes)}")
    print(f"Disabled Swagger scaffolds to add: {len(additions)}")


if __name__ == "__main__":
    main()
