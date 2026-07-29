from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TestCase:
    """Legacy test case without service awareness."""

    tc_id: str
    description: str
    bank: str
    api_name: str
    request_file: str
    expected_result: str
    validation_type: str
    execute: str
    flow_config: str = ""
    validation_rules: str = ""


@dataclass
class ServiceTestCase:
    """Service-aware test case with service context."""

    tc_id: str
    service: str
    description: str
    bank: str
    api_name: str
    request_file: str
    expected_result: str
    validation_type: str
    execute: str
    flow_config: str = ""
    validation_rules: str = ""
    test_type: str = "positive"
    trx_type: str = "non-financial"
