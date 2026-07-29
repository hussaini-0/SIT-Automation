"""DQRC upload parsing and runtime RTP ID storage."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from services.config_service import CONFIG_DIR, load_yaml, write_yaml


RUNTIME_TEST_DATA_FILE = CONFIG_DIR / "runtime_test_data.yaml"
RTP_ID_KEYS = ("rtpId", "rtp_id", "RTP_ID", "rtpid", "rtpID")


def extract_dqrc_details(raw_bytes: bytes, filename: str = "") -> dict[str, str]:
    text = raw_bytes.decode("utf-8", errors="ignore").strip()
    details: dict[str, str] = {"source_file": filename}
    if not text:
        return details

    parsed = _try_parse_json(text)
    if parsed is not None:
        rtp_id = _find_key_recursive(parsed, set(RTP_ID_KEYS))
        if rtp_id:
            details["RTP_ID"] = str(rtp_id).strip()

    if "RTP_ID" not in details:
        rtp_id = _extract_rtp_id_from_text(text)
        if rtp_id:
            details["RTP_ID"] = rtp_id

    if text:
        details["raw_dqrc"] = text[:5000]
    return details


def save_dqrc_runtime_details(details: dict[str, str]) -> None:
    rtp_id = str(details.get("RTP_ID", "")).strip()
    if not rtp_id:
        raise ValueError("DQRC upload did not contain an RTP ID.")

    current = load_yaml(RUNTIME_TEST_DATA_FILE)
    current["RTP_ID"] = rtp_id
    current["RTP_ID_UNIQUE"] = rtp_id
    current["DQRC_RTP_ID"] = rtp_id
    if details.get("source_file"):
        current["DQRC_SOURCE_FILE"] = details["source_file"]
    write_yaml(RUNTIME_TEST_DATA_FILE, current)


def load_runtime_rtp_id() -> str:
    current = load_yaml(RUNTIME_TEST_DATA_FILE)
    return str(current.get("RTP_ID", "") or "").strip()


def _try_parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _find_key_recursive(value: Any, keys: set[str]) -> Any | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in keys and item not in (None, ""):
                return item
        for item in value.values():
            found = _find_key_recursive(item, keys)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_key_recursive(item, keys)
            if found not in (None, ""):
                return found
    return None


def _extract_rtp_id_from_text(text: str) -> str:
    patterns = [
        r'"(?:rtpId|rtp_id|RTP_ID|rtpid|rtpID)"\s*:\s*"([^"]+)"',
        r"(?:rtpId|rtp_id|RTP_ID|rtpid|rtpID)\s*[=:]\s*([A-Za-z0-9_.:-]{8,100})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""
