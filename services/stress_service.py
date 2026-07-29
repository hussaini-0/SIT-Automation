"""Background stress execution service for the dashboard."""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from runner import SITRunner
from services.config_service import ROOT_DIR, load_yaml
from utils.stress_runner import StressOptions, run_stress


@dataclass
class StressExecutionState:
    job_id: str
    status: str = "queued"
    started_at: str = ""
    finished_at: str = ""
    scenario_name: str = ""
    total_requests: int = 0
    passed: int = 0
    failed: int = 0
    requests_per_second: float = 0.0
    p95_ms: int = 0
    report_file: str = ""
    result_file: str = ""
    error: str = ""
    options: dict[str, Any] = field(default_factory=dict)


_jobs: dict[str, StressExecutionState] = {}
_jobs_lock = threading.Lock()


def load_stress_scenarios() -> dict[str, dict[str, Any]]:
    stress_config = load_yaml(ROOT_DIR / "config" / "stress.yaml")
    scenarios = stress_config.get("scenarios", {})
    return scenarios if isinstance(scenarios, dict) else {}


def start_stress_execution(options: StressOptions) -> str:
    job_id = uuid.uuid4().hex[:12]
    state = StressExecutionState(
        job_id=job_id,
        scenario_name=options.scenario_name,
        options=asdict(options),
    )
    with _jobs_lock:
        _jobs[job_id] = state
    thread = threading.Thread(target=_run_job, args=(job_id, options), daemon=True)
    thread.start()
    return job_id


def get_stress_execution_state(job_id: str) -> StressExecutionState | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def _run_job(job_id: str, options: StressOptions) -> None:
    state = get_stress_execution_state(job_id)
    if state is None:
        return

    state.status = "running"
    state.started_at = datetime.now().isoformat(timespec="seconds")
    try:
        runner = SITRunner(ROOT_DIR)
        output = run_stress(runner, options)
        summary = output.get("summary", {})
        run_tag = str(output.get("run_tag", "") or "")
        scenario_name = str(output.get("scenario", "") or "").strip()
        service_tag = runner._build_service_artifact_tag(output.get("results", []))
        extra_tag = "-".join(
            part for part in [runner._slugify_label(scenario_name) if scenario_name else "", service_tag] if part
        )
        state.total_requests = int(summary.get("total_requests", 0) or 0)
        state.passed = int(summary.get("passed", 0) or 0)
        state.failed = int(summary.get("failed", 0) or 0)
        state.requests_per_second = float(summary.get("requests_per_second", 0.0) or 0.0)
        state.p95_ms = int(summary.get("p95_ms", 0) or 0)
        state.result_file = str(
            ROOT_DIR / "results" / "stress" / runner._artifact_file_name("stress_results", run_tag, "json", extra_tag)
        )
        state.report_file = str(
            ROOT_DIR / "reports" / "stress" / runner._artifact_file_name("stress_report", run_tag, "html", extra_tag)
        )
        state.status = "completed"
        state.finished_at = datetime.now().isoformat(timespec="seconds")
    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        state.finished_at = datetime.now().isoformat(timespec="seconds")
