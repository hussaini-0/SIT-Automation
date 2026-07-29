"""Configuration helpers for the QA Control Center."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os
import tempfile
import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
DASHBOARD_SETTINGS_FILE = CONFIG_DIR / "dashboard_settings.yaml"


@dataclass(frozen=True)
class DashboardSettings:
    environment: str = "SIT"
    default_workers: int = 4
    default_timeout: int = 30
    default_retries: int = 2
    default_report_location: str = "reports"
    default_result_location: str = "results"
    verbose_logging: bool = False


def resolve_yaml_path(path: Path) -> Path:
    if path.exists():
        return path
    if path.suffix.lower() in {".yaml", ".yml"}:
        example_path = path.with_name(f"{path.stem}.example{path.suffix}")
        if example_path.exists():
            return example_path
    return path


def load_yaml(path: Path) -> dict[str, Any]:
    resolved_path = resolve_yaml_path(path)
    if not resolved_path.exists():
        return {}
    with resolved_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def load_settings() -> DashboardSettings:
    data = load_yaml(DASHBOARD_SETTINGS_FILE)
    api_defaults = load_yaml(CONFIG_DIR / "apis.yaml").get("defaults", {})
    return DashboardSettings(
        environment=str(data.get("environment", "SIT")),
        default_workers=int(data.get("default_workers", 4)),
        default_timeout=int(data.get("default_timeout", api_defaults.get("timeout_seconds", 30))),
        default_retries=int(data.get("default_retries", api_defaults.get("retries", 2))),
        default_report_location=str(data.get("default_report_location", "reports")),
        default_result_location=str(data.get("default_result_location", "results")),
        verbose_logging=bool(data.get("verbose_logging", False)),
    )


def save_settings(settings: DashboardSettings) -> None:
    write_yaml(
        DASHBOARD_SETTINGS_FILE,
        {
            "environment": settings.environment,
            "default_workers": settings.default_workers,
            "default_timeout": settings.default_timeout,
            "default_retries": settings.default_retries,
            "default_report_location": settings.default_report_location,
            "default_result_location": settings.default_result_location,
            "verbose_logging": settings.verbose_logging,
        },
    )

    api_path = CONFIG_DIR / "apis.yaml"
    api_config = load_yaml(api_path)
    api_config.setdefault("defaults", {})
    api_config["defaults"]["timeout_seconds"] = settings.default_timeout
    api_config["defaults"]["retries"] = settings.default_retries
    write_yaml(api_path, api_config)


def get_services_config() -> dict[str, Any]:
    servers = load_yaml(CONFIG_DIR / "servers.yaml")
    apis = load_yaml(CONFIG_DIR / "apis.yaml")
    services: dict[str, Any] = {}
    for service_id in set(servers.get("services", {})) | set(apis.get("services", {})):
        server_item = dict(servers.get("services", {}).get(service_id, {}) or {})
        api_item = dict(apis.get("services", {}).get(service_id, {}) or {})
        services[service_id] = {
            **server_item,
            **{k: v for k, v in api_item.items() if k in {"display_name", "auth", "apis", "token_routing", "flows"}},
        }
    return services


def get_banks_config() -> dict[str, Any]:
    servers = load_yaml(CONFIG_DIR / "servers.yaml")
    return dict(servers.get("banks", {}) or {})


def update_service_enabled(service_id: str, enabled: bool) -> None:
    path = CONFIG_DIR / "servers.yaml"
    data = load_yaml(path)
    data.setdefault("services", {}).setdefault(service_id, {})["enabled"] = enabled
    write_yaml(path, data)


def normalize_service_id(value: str) -> str:
    service_id = value.strip().lower().replace("-", "_").replace(" ", "_")
    return "_".join(part for part in service_id.split("_") if part)


def ensure_service(service_id: str, display_name: str, base_url: str = "", enabled: bool = False) -> str:
    normalized_id = normalize_service_id(service_id)
    if not normalized_id:
        raise ValueError("Service ID is required.")

    servers_path = CONFIG_DIR / "servers.yaml"
    servers = load_yaml(servers_path)
    server_entry = servers.setdefault("services", {}).setdefault(normalized_id, {})
    server_entry.setdefault("display_name", display_name.strip() or normalized_id)
    server_entry.setdefault("base_url", base_url.strip())
    server_entry.setdefault("enabled", enabled)
    if display_name.strip():
        server_entry["display_name"] = display_name.strip()
    if base_url.strip():
        server_entry["base_url"] = base_url.strip()
    write_yaml(servers_path, servers)

    apis_path = CONFIG_DIR / "apis.yaml"
    apis = load_yaml(apis_path)
    api_entry = apis.setdefault("services", {}).setdefault(normalized_id, {})
    api_entry.setdefault("display_name", display_name.strip() or normalized_id)
    api_entry.setdefault("auth", {"apis": [], "token_json_path": "token"})
    api_entry.setdefault("token_routing", {})
    api_entry.setdefault("apis", {})
    if display_name.strip():
        api_entry["display_name"] = display_name.strip()
    write_yaml(apis_path, apis)

    requests_dir = ROOT_DIR / "requests" / normalized_id
    requests_dir.mkdir(parents=True, exist_ok=True)
    return normalized_id
