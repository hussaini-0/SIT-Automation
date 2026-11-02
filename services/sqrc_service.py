"""SQRC payload parsing and runtime merchant-data storage."""

from __future__ import annotations

import json
import re
from typing import Any

from services.config_service import CONFIG_DIR, load_yaml, write_yaml


RUNTIME_TEST_DATA_FILE = CONFIG_DIR / "runtime_test_data.yaml"
SQRC_PROFILES_FILE = CONFIG_DIR / "sqrc_profiles.yaml"

_FIELD_ALIASES = {
    "MERCHANT_ACCOUNT_TITLE": {"accounttitle", "merchantname", "merchanttitle"},
    "MERCHANT_DBA": {"dba", "dbaname", "dbaname"},
    "MERCHANT_CATEGORY_CODE": {"categorycode", "merchantcategorycode", "mcc", "merchantmcc"},
    "MERCHANT_BIC": {"bic", "memberid", "participantcode", "receiverparticipantcode"},
    "MERCHANT_IBAN": {"iban", "merchantiban", "merchantaccountiban"},
    "MERCHANT_ID_ALIAS": {"merchantidalias", "alias", "merchantalias"},
    "MERCHANT_CURRENCY": {"currency", "currencycode"},
    "MERCHANT_COUNTRY": {"country", "countrycode"},
    "MERCHANT_CITY": {"city", "cityname", "townname"},
    "MERCHANT_STORE_LABEL": {"storelabel", "subdept", "terminallabel"},
    "MERCHANT_TERMINAL_ID": {"terminalid", "terminal", "terminalidentifier"},
}


def extract_sqrc_details(raw_bytes: bytes, filename: str = "") -> dict[str, str]:
    """Extract known merchant fields from JSON, key/value text, or QR text."""
    text = raw_bytes.decode("utf-8", errors="ignore").strip()
    details: dict[str, str] = {"SQRC_SOURCE_FILE": filename}
    if not text:
        return details

    parsed = _try_parse_json(text)
    values = _flatten_values(parsed) if parsed is not None else _key_value_values(text)
    if parsed is None:
        values.update(_parse_emv_qr(text))
    for token, aliases in _FIELD_ALIASES.items():
        value = values.get(token, "") or _first_alias_value(values, aliases)
        if value:
            details[token] = value

    details["SQRC_RAW"] = text[:10000]
    return details


def extract_sqrc_image(raw_bytes: bytes, filename: str = "") -> dict[str, str]:
    """Decode a QR image using several size/contrast variants."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ValueError("Image QR decoding needs opencv-python-headless. Install project requirements first.") from exc

    image = cv2.imdecode(np.frombuffer(raw_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("The uploaded file is not a readable image.")

    decoded: list[str] = []
    height, width = image.shape[:2]
    scale = min(1.0, 2400 / max(height, width))
    base = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image
    gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
    variants = [
        image,
        base,
        gray,
        cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC),
        cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1],
        cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 5),
    ]
    # A QR embedded in a large poster can be too small for whole-image detection.
    # Scan overlapping tiles at the source resolution as well.
    for rows, columns in ((2, 2), (3, 3)):
        tile_height = height // rows
        tile_width = width // columns
        for row in range(rows):
            for column in range(columns):
                y0 = max(0, row * tile_height - tile_height // 6)
                y1 = min(height, (row + 1) * tile_height + tile_height // 6)
                x0 = max(0, column * tile_width - tile_width // 6)
                x1 = min(width, (column + 1) * tile_width + tile_width // 6)
                tile = image[y0:y1, x0:x1]
                if tile.size:
                    variants.append(tile)
    # Use overlapping square windows as a final pass. This handles screenshots
    # where the QR is small and crosses a regular grid boundary.
    side = min(max(320, min(height, width) // 2), 600)
    step = max(160, side // 2)
    for y0 in range(0, max(1, height - side + 1), step):
        for x0 in range(0, max(1, width - side + 1), step):
            variants.append(image[y0:min(height, y0 + side), x0:min(width, x0 + side)])
    if height > side or width > side:
        variants.append(image[max(0, height - side):height, max(0, width - side):width])
    # Screenshots often place the QR on a bright card over a dark page. Isolate
    # bright card regions so the detector does not have to process the whole UI.
    bright = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)[1]
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        if box_width * box_height < 1000:
            continue
        padding = 12
        x0, y0 = max(0, x - padding), max(0, y - padding)
        x1, y1 = min(width, x + box_width + padding), min(height, y + box_height + padding)
        variants.append(image[y0:y1, x0:x1])
    detector = cv2.QRCodeDetector()
    for variant in variants:
        try:
            ok, values, _points, _straight = detector.detectAndDecodeMulti(variant)
            if ok:
                decoded.extend(str(value) for value in values if str(value).strip())
        except cv2.error:
            pass
        if decoded:
            break
        try:
            value, _points, _straight = detector.detectAndDecode(variant)
            if value and value.strip():
                decoded.append(value.strip())
                break
        except cv2.error:
            pass
    if not decoded:
        raise ValueError("No readable QR code was found in the uploaded image.")

    details = extract_sqrc_details(decoded[0].encode("utf-8"), filename)
    details["SQRC_QR_PAYLOAD"] = decoded[0]
    return details


def save_sqrc_runtime_details(details: dict[str, str], bank: str = "") -> dict[str, str]:
    required = ("MERCHANT_BIC", "MERCHANT_IBAN")
    missing = [key for key in required if not str(details.get(key, "")).strip()]
    if missing:
        raise ValueError(f"SQRC is missing required field(s): {', '.join(missing)}")

    current = load_yaml(RUNTIME_TEST_DATA_FILE)
    for key, value in details.items():
        if value not in (None, ""):
            current[key] = str(value).strip()
    if bank:
        current["SQRC_BANK"] = bank
    write_yaml(RUNTIME_TEST_DATA_FILE, current)
    return current


def save_sqrc_profile(
    details: dict[str, str],
    profile_name: str,
    bank: str = "",
) -> dict[str, dict[str, str]]:
    """Save a named SQRC profile while keeping the legacy active profile updated."""
    name = str(profile_name or details.get("SQRC_SOURCE_FILE", "SQRC") or "SQRC").strip()
    if not name:
        raise ValueError("SQRC profile name is required")
    profile = {key: str(value).strip() for key, value in details.items() if value not in (None, "")}
    if bank:
        profile["SQRC_BANK"] = bank
    profiles = load_yaml(SQRC_PROFILES_FILE)
    if not isinstance(profiles, dict):
        profiles = {}
    profiles[name] = profile
    write_yaml(SQRC_PROFILES_FILE, profiles)
    save_sqrc_runtime_details(profile, bank)
    return {str(key): value for key, value in profiles.items() if isinstance(value, dict)}


def load_sqrc_runtime_details() -> dict[str, str]:
    current = load_yaml(RUNTIME_TEST_DATA_FILE)
    return {key: str(value) for key, value in current.items() if str(key).startswith("MERCHANT_") or str(key).startswith("SQRC_")}


def load_sqrc_profiles() -> dict[str, dict[str, str]]:
    profiles = load_yaml(SQRC_PROFILES_FILE)
    if not isinstance(profiles, dict):
        return {}
    return {
        str(name): {str(key): str(value) for key, value in values.items() if value is not None}
        for name, values in profiles.items()
        if isinstance(values, dict)
    }


def load_sqrc_profile(profile_name: str = "") -> dict[str, str]:
    if profile_name:
        profile = load_sqrc_profiles().get(profile_name, {})
        if profile:
            return profile
    return load_sqrc_runtime_details()


def build_sqrc_request_body(details: dict[str, str]) -> dict[str, Any]:
    """Build the readable SQRC request shape from extracted merchant fields."""
    return {
        "merchantInfo": {
            "accountTitle": details.get("MERCHANT_ACCOUNT_TITLE", ""),
            "dba": details.get("MERCHANT_DBA", details.get("MERCHANT_ACCOUNT_TITLE", "")),
            "categoryCode": details.get("MERCHANT_CATEGORY_CODE", ""),
            "bic": details.get("MERCHANT_BIC", ""),
            "iban": details.get("MERCHANT_IBAN", ""),
            "merchantIdAlias": details.get("MERCHANT_ID_ALIAS", ""),
        },
        "additionalInfo": {
            "currency": details.get("MERCHANT_CURRENCY", ""),
            "country": details.get("MERCHANT_COUNTRY", ""),
            "city": details.get("MERCHANT_CITY", ""),
            "storeLabel": details.get("MERCHANT_STORE_LABEL", ""),
            "terminalID": details.get("MERCHANT_TERMINAL_ID", ""),
        },
    }


def _try_parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _normalise_key(key: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _flatten_values(value: Any) -> dict[str, str]:
    found: dict[str, str] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                found.update(_flatten_values(item))
            elif item not in (None, ""):
                found.setdefault(_normalise_key(key), str(item).strip())
    elif isinstance(value, list):
        for item in value:
            found.update(_flatten_values(item))
    return found


def _key_value_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in re.split(r"[&\n,;]", text):
        if "=" not in part and ":" not in part:
            continue
        key, value = re.split(r"[=:]", part, maxsplit=1)
        value = value.strip().strip('"')
        if key.strip() and value:
            values.setdefault(_normalise_key(key), value)
    return values


def _parse_emv_qr(text: str) -> dict[str, str]:
    """Map EMV merchant-presented QR tags to readable SQRC fields."""
    fields: dict[str, str] = {}
    tags = _parse_tlv(text)
    if not tags:
        return fields
    tag_names = {
        "00": "SQRC_FORMAT",
        "01": "SQRC_POINT_OF_INITIATION",
        "52": "MERCHANT_CATEGORY_CODE",
        "53": "MERCHANT_CURRENCY",
        "58": "MERCHANT_COUNTRY",
        "59": "MERCHANT_ACCOUNT_TITLE",
        "60": "MERCHANT_CITY",
    }
    for tag, value in tags.items():
        if tag in tag_names:
            fields[tag_names[tag]] = value
    merchant_account = tags.get("28") or tags.get("29")
    if merchant_account:
        account_tags = _parse_tlv(merchant_account)
        fields.update(
            {
                "MERCHANT_ID_ALIAS": account_tags.get("00", ""),
                "MERCHANT_BIC": account_tags.get("01", ""),
                "MERCHANT_IBAN": account_tags.get("02", ""),
            }
        )
    additional = _parse_tlv(tags.get("62", ""))
    if additional.get("03"):
        fields["MERCHANT_STORE_LABEL"] = additional["03"]
    if additional.get("07"):
        fields["MERCHANT_TERMINAL_ID"] = additional["07"]
    return {key: value for key, value in fields.items() if value}


def _parse_tlv(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    index = 0
    while index + 4 <= len(text):
        tag = text[index:index + 2]
        try:
            length = int(text[index + 2:index + 4])
        except ValueError:
            break
        start = index + 4
        end = start + length
        if end > len(text):
            # Preserve valid fields before a truncated trailing CRC/payload.
            break
        values[tag] = text[start:end]
        index = end
    return values


def _first_alias_value(values: dict[str, str], aliases: set[str]) -> str:
    for key, value in values.items():
        if _normalise_key(key) in {_normalise_key(alias) for alias in aliases}:
            return value
    for alias in aliases:
        value = values.get(_normalise_key(alias), "")
        if value:
            return value
    return ""
