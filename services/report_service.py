"""Report, result, history, and log readers for the dashboard."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from services.config_service import ROOT_DIR


RESULTS_DIR = ROOT_DIR / "results"
REPORTS_DIR = ROOT_DIR / "reports"
LOGS_DIR = ROOT_DIR / "logs"
HISTORY_FILE = RESULTS_DIR / "execution_history.json"
STRESS_RESULTS_DIR = RESULTS_DIR / "stress"
STRESS_REPORTS_DIR = REPORTS_DIR / "stress"


@dataclass(frozen=True)
class RunArtifact:
    run_tag: str
    path: Path
    kind: str
    modified_at: datetime


def list_reports() -> list[RunArtifact]:
    return _list_artifacts(REPORTS_DIR, "report_*.html", "HTML")


def list_results() -> list[RunArtifact]:
    artifacts = _list_artifacts(RESULTS_DIR, "results_*.json", "JSON")
    artifacts.extend(_list_artifacts(RESULTS_DIR, "results_*.csv", "CSV"))
    return sorted(artifacts, key=lambda artifact: artifact.modified_at, reverse=True)


def list_stress_reports() -> list[RunArtifact]:
    return _list_artifacts(STRESS_REPORTS_DIR, "stress_report_*.html", "HTML")


def list_stress_results() -> list[RunArtifact]:
    artifacts = _list_artifacts(STRESS_RESULTS_DIR, "stress_results_*.json", "JSON")
    artifacts.extend(_list_artifacts(STRESS_RESULTS_DIR, "stress_results_*.csv", "CSV"))
    return sorted(artifacts, key=lambda artifact: artifact.modified_at, reverse=True)


def _list_artifacts(directory: Path, pattern: str, kind: str) -> list[RunArtifact]:
    if not directory.exists():
        return []
    artifacts = []
    for path in directory.glob(pattern):
        stem = path.stem.replace("report_", "").replace("results_", "")
        artifacts.append(RunArtifact(stem, path, kind, datetime.fromtimestamp(path.stat().st_mtime)))
    return sorted(artifacts, key=lambda artifact: artifact.modified_at, reverse=True)


def latest_result() -> dict[str, Any]:
    for artifact in list_results():
        if artifact.kind != "JSON":
            continue
        result = read_result(artifact.path)
        if result:
            return result
    return {}


def read_result(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}


def read_text(path: Path, max_chars: int | None = 200_000) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is None:
        return text
    return text[-max_chars:]


def available_logs() -> list[Path]:
    if not LOGS_DIR.exists():
        return []
    return sorted(LOGS_DIR.glob("*.log"), key=lambda path: path.name)


def append_history(entry: dict[str, Any]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    history = load_history()
    history.insert(0, entry)
    _atomic_write_json(HISTORY_FILE, history[:200])


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def summarize_latest() -> dict[str, Any]:
    result = latest_result()
    summary = result.get("summary", {}) if result else {}
    latest_report = list_reports()[0].path.name if list_reports() else ""
    return {
        "last_execution": result.get("run_tag", ""),
        "latest_report": latest_report,
        "pass_percent": float(summary.get("pass_percent", 0.0) or 0.0),
        "total": int(summary.get("total", 0) or 0),
        "passed": int(summary.get("passed", 0) or 0),
        "failed": int(summary.get("failed", 0) or 0),
        "skipped": int(summary.get("skipped", 0) or 0),
    }
