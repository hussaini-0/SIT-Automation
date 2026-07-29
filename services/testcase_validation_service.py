"""Static testcase checks used before dashboard execution starts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from runner import SITRunner
from services.config_service import ROOT_DIR
from services.testcase_service import TestcaseRecord
from utils.template_engine import TemplateEngine


UNRESOLVED_PLACEHOLDER_PATTERN = re.compile(r"\$\{[A-Z0-9_]+\}")


@dataclass(frozen=True)
class TestcaseValidationIssue:
    tc_id: str
    service: str
    bank: str
    api_name: str
    severity: str
    message: str


def validate_records_for_run(records: list[TestcaseRecord]) -> list[TestcaseValidationIssue]:
    """Validate request files, API config, bank URLs, and unresolved placeholders."""
    runner = SITRunner(ROOT_DIR)
    issues: list[TestcaseValidationIssue] = []

    for record in records:
        issues.extend(_validate_record(runner, record))

    return issues


def _validate_record(runner: SITRunner, record: TestcaseRecord) -> list[TestcaseValidationIssue]:
    issues: list[TestcaseValidationIssue] = []

    def issue(message: str, severity: str = "error") -> None:
        issues.append(
            TestcaseValidationIssue(
                tc_id=record.tc_id,
                service=record.service,
                bank=record.bank,
                api_name=record.api_name,
                severity=severity,
                message=message,
            )
        )

    try:
        runner._get_api_definition(record.api_name, record.service)
    except Exception as exc:
        issue(str(exc))

    try:
        runner._get_bank_base_url(record.bank, record.service)
    except Exception as exc:
        issue(str(exc))

    if not record.request_file:
        return issues

    request_path = runner.requests_dir / record.service / record.request_file
    if not request_path.exists():
        request_path = runner.requests_dir / record.request_file
    if not request_path.exists():
        issue(f"Request file not found: {record.request_file}")
        return issues

    try:
        template = TemplateEngine.load_json_template(request_path)
    except json.JSONDecodeError as exc:
        issue(f"Request file is not valid JSON: {exc}")
        return issues
    except OSError as exc:
        issue(f"Request file could not be read: {exc}")
        return issues

    try:
        rendered_payload = runner._render_payload(
            record.request_file,
            extra_tokens={},
            service=record.service,
            bank_name=record.bank,
        )
    except Exception as exc:
        issue(f"Request payload could not be rendered: {exc}")
        return issues

    unresolved = sorted(_find_unresolved_placeholders(rendered_payload))
    if unresolved:
        issue(f"Unresolved test data placeholder(s): {', '.join(unresolved)}")

    if record.flow_config:
        flows = runner.service_api_config.get(record.service, {}).get("flows", {}) or {}
        if record.flow_config not in flows:
            issue(f"Flow_Config not found for service '{record.service}': {record.flow_config}")

    return issues


def _find_unresolved_placeholders(value: Any) -> set[str]:
    if isinstance(value, dict):
        tokens: set[str] = set()
        for item in value.values():
            tokens.update(_find_unresolved_placeholders(item))
        return tokens
    if isinstance(value, list):
        tokens: set[str] = set()
        for item in value:
            tokens.update(_find_unresolved_placeholders(item))
        return tokens
    if isinstance(value, str):
        return set(UNRESOLVED_PLACEHOLDER_PATTERN.findall(value))
    return set()
