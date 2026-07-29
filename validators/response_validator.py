import json
from typing import Any, Dict, Optional


class ResponseValidator:
    MESSAGE_ALIASES = {
        "invalid gender": [
            "invalid gender",
            "invalid gender, accepted values( male/fema/trns)",
        ],
        "amount decimal value": [
            "json parse error: amount must be a decimal value (e.g. 0.0, 10.50). integer values like 0 or 10 are not allowed.",
            "json parse error: amount must be a decimal up to 2 decimal places (e.g. 0.0, 10.50). integer or other values like 0, 10 or abc are not allowed.",
            "decimal value",
        ],
        "amount valid decimal": [
            "minimum amount allowed: 0",
            "json parse error: amount must be a valid decimal number (e.g. 0.0, 5.25, 10.15) with up to 2 decimal places",
            "valid decimal number",
        ],
    }

    def __init__(self, validation_logger) -> None:
        self.validation_logger = validation_logger

    def validate(
        self,
        validation_type: str,
        expected_result: str,
        response: Dict[str, Any],
        validation_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validation_type = (validation_type or "response").strip().lower()
        rules = validation_rules or {}

        if validation_type == "status_code":
            return self._validate_status_code(expected_result, response)
        if validation_type == "json_field":
            return self._validate_json_field(expected_result, response, rules)
        if validation_type == "response":
            return self._validate_response_contains(expected_result, response, rules)

        self.validation_logger.warning("Unknown validation_type=%s; fallback to response", validation_type)
        return self._validate_response_contains(expected_result, response, rules)

    def _validate_status_code(self, expected_result: str, response: Dict[str, Any]) -> Dict[str, Any]:
        expected_text = str(expected_result).strip()
        if not expected_text.isdigit():
            actual = (
                "Invalid status_code expected_result. "
                f"Expected a number like 200 or 400, got: {expected_text}"
            )
            self.validation_logger.warning(
                "STATUS_CODE_VALIDATION_CONFIG_ERROR | expected=%s",
                expected_text,
            )
            return {"passed": False, "actual": actual}

        expected_code = int(expected_text)
        actual_code = response.get("status_code")
        passed = actual_code == expected_code
        actual = str(actual_code)
        self.validation_logger.info(
            "STATUS_CODE_VALIDATION | expected=%s | actual=%s | passed=%s",
            expected_code,
            actual,
            passed,
        )
        return {"passed": passed, "actual": actual}

    def _validate_json_field(
        self,
        expected_result: str,
        response: Dict[str, Any],
        validation_rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        body = response.get("body", {})
        field_path = validation_rules.get("field")

        if not field_path:
            if ":" in expected_result:
                field_path, expected_result = expected_result.split(":", 1)
            else:
                return {"passed": False, "actual": "Missing field rule for json_field validation"}

        actual_value = self._get_path_value(body, field_path.strip())
        expected_value = expected_result.strip()
        passed = str(actual_value) == expected_value
        self.validation_logger.info(
            "JSON_FIELD_VALIDATION | field=%s | expected=%s | actual=%s | passed=%s",
            field_path,
            expected_value,
            actual_value,
            passed,
        )
        return {"passed": passed, "actual": str(actual_value)}

    def _validate_response_contains(
        self,
        expected_result: str,
        response: Dict[str, Any],
        validation_rules: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # Normalize inputs
        expected = str(expected_result).strip()
        rules = validation_rules or {}
        text = response.get("text", "") or ""
        body = response.get("body", {})
        body_text = json.dumps(body, ensure_ascii=False)

        any_of = rules.get("any_of") if isinstance(rules, dict) else None
        if isinstance(any_of, list) and any_of:
            actual = body_text if len(body_text) <= 1000 else body_text[:1000] + "..."
            passed = any(
                bool(str(option).strip())
                and (str(option).strip() in text or str(option).strip() in body_text)
                for option in any_of
            )
            self.validation_logger.info(
                "RESPONSE_VALIDATION_ANY_OF | expected_any_of=%s | passed=%s",
                any_of,
                passed,
            )
            return {"passed": passed, "actual": actual}

        # Backward-compat: if expected is a single message (no commas), use substring match.
        if "," not in expected:
            expected_normalized = self._normalize_message(expected)
            text_normalized = self._normalize_message(text)
            body_text_normalized = self._normalize_message(body_text)
            passed = (
                expected_normalized in text_normalized
                or expected_normalized in body_text_normalized
                or self._messages_equivalent(expected, text)
                or self._messages_equivalent(expected, body_text)
            )
            actual = body_text if len(body_text) <= 1000 else body_text[:1000] + "..."
            self.validation_logger.info(
                "RESPONSE_VALIDATION | expected_contains=%s | passed=%s",
                expected,
                passed,
            )
            return {"passed": passed, "actual": actual}

        # Helper: collect all string leaf values from the body (dicts/lists) so we
        # can split the actual message values reliably by commas even when the body
        # is JSON-encoded.
        def _collect_strings(node: Any) -> list:
            parts = []
            if isinstance(node, str):
                parts.append(node)
            elif isinstance(node, dict):
                for v in node.values():
                    parts.extend(_collect_strings(v))
            elif isinstance(node, list):
                for item in node:
                    parts.extend(_collect_strings(item))
            else:
                # convert other leaf types to string
                if node is not None:
                    parts.append(str(node))
            return parts

        # 1. Split expected into normalized set of messages
        expected_parts = [self._normalize_message(p) for p in expected.split(",")]
        expected_set = {p for p in expected_parts if p}

        # 2. Build actual message pool: include `text` and all string leaf values from `body`.
        actual_values = []
        if text:
            actual_values.append(text)
        actual_values.extend(_collect_strings(body))

        # Join the collected actual strings with commas and split to normalize messages.
        combined_actual_source = ",".join(actual_values)
        actual_parts = [self._normalize_message(p) for p in combined_actual_source.split(",")]
        actual_set = {p for p in actual_parts if p}

        # 3. Check that all expected messages appear among the actual messages (order-independent).
        passed = expected_set.issubset(actual_set) or all(
            any(self._messages_equivalent(expected_part, actual_part) for actual_part in actual_set)
            for expected_part in expected_set
        )

        actual = body_text if len(body_text) <= 1000 else body_text[:1000] + "..."
        self.validation_logger.info(
            "RESPONSE_VALIDATION | expected_contains=%s | passed=%s",
            expected,
            passed,
        )
        return {"passed": passed, "actual": actual}

    @staticmethod
    def _get_path_value(payload: Any, path: str) -> Any:
        current = payload
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _normalize_message(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        return " ".join(text.split())

    @classmethod
    def _message_tokens(cls, value: Any) -> set[str]:
        normalized = cls._normalize_message(value)
        if not normalized:
            return set()
        tokens = {normalized}
        for canonical, variants in cls.MESSAGE_ALIASES.items():
            canonical_normalized = cls._normalize_message(canonical)
            variant_set = {cls._normalize_message(item) for item in variants}
            if normalized == canonical_normalized or normalized in variant_set:
                tokens.add(canonical_normalized)
                tokens.update(variant_set)
        return tokens

    @classmethod
    def _messages_equivalent(cls, expected: Any, actual: Any) -> bool:
        expected_tokens = cls._message_tokens(expected)
        actual_normalized = cls._normalize_message(actual)
        if not expected_tokens or not actual_normalized:
            return False
        if any(token and token in actual_normalized for token in expected_tokens):
            return True
        actual_tokens = cls._message_tokens(actual)
        return bool(expected_tokens & actual_tokens)
