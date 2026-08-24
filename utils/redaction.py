"""Redact sensitive values before persisting reports/results."""

from __future__ import annotations

import copy
import re
from typing import Any


JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
PK_IBAN_PATTERN = re.compile(r"\bPK[0-9]{2}[A-Z0-9]{8,30}\b")
LONG_DIGIT_PATTERN = re.compile(r"\b\d{10,}\b")
SENSITIVE_KEYS = {"authorization", "password", "token", "jwt", "access_token", "refresh_token"}


def redact_sensitive(value: Any) -> Any:
    """Return a sanitized deep copy with tokens, passwords, IBANs, and long IDs masked."""
    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if "password" in key_text:
                redacted[key] = "[REDACTED]"
            elif key_text in SENSITIVE_KEYS or key_text.endswith("_token"):
                redacted[key] = _redact_secret_text(str(item))
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _redact_secret_text(value)
    return copy.deepcopy(value)


def _redact_secret_text(text: str) -> str:
    redacted = JWT_PATTERN.sub("[REDACTED_JWT]", text)
    redacted = PK_IBAN_PATTERN.sub(_mask_iban, redacted)
    redacted = LONG_DIGIT_PATTERN.sub(_mask_long_number, redacted)
    if redacted.lower().startswith("bearer "):
        return "Bearer [REDACTED]"
    if redacted.lower().startswith("basic "):
        return "Basic [REDACTED]"
    return redacted


def _mask_iban(match: re.Match[str]) -> str:
    value = match.group(0)
    return f"{value[:4]}[REDACTED]{value[-4:]}"


def _mask_long_number(match: re.Match[str]) -> str:
    value = match.group(0)
    return f"{value[:3]}[REDACTED]{value[-3:]}"
