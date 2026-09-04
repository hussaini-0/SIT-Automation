"""Background execution service for selected dashboard test runs."""

from __future__ import annotations

import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Any

from runner import SITRunner
from utils.api_client import ApiClient
from services.config_service import ROOT_DIR
from services.report_service import append_history
from services.testcase_service import (
    TestcaseRecord,
    load_testcase_inventory,
    select_testcase_inventory,
    to_runner_testcase,
)


@dataclass(frozen=True)
class ExecutionOptions:
    services: list[str]
    apis: list[str] = field(default_factory=list)
    testcase_ids: list[str] = field(default_factory=list)
    testcase_keys: list[str] = field(default_factory=list)
    bank: str = ""
    workers: int = 4
    timeout: int = 30
    retries: int = 2
    parallel: bool = True
    environment: str = "SIT"
    verbose_logging: bool = False
    include_disabled: bool = False
    exclude_dqrc: bool = False


@dataclass
class ExecutionState:
    job_id: str
    status: str = "queued"
    started_at: str = ""
    finished_at: str = ""
    current_api: str = ""
    current_testcase: str = ""
    total: int = 0
    completed: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    run_tag: str = ""
    report_file: str = ""
    result_file: str = ""
    error: str = ""
    cancel_requested: bool = False
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def percent(self) -> float:
        return round((self.completed / self.total) * 100, 2) if self.total else 0.0


_jobs: dict[str, ExecutionState] = {}
_jobs_lock = threading.Lock()


def start_execution(options: ExecutionOptions) -> str:
    job_id = uuid.uuid4().hex[:12]
    state = ExecutionState(job_id=job_id, options=asdict(options))
    with _jobs_lock:
        _jobs[job_id] = state
    thread = threading.Thread(target=_run_job, args=(job_id, options), daemon=True)
    thread.start()
    return job_id


def get_execution_state(job_id: str) -> ExecutionState | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def cancel_execution(job_id: str) -> bool:
    with _jobs_lock:
        state = _jobs.get(job_id)
        if state is None or state.status not in {"queued", "running"}:
            return False
        state.cancel_requested = True
        state.status = "stopping"
        return True


def _select_records(options: ExecutionOptions) -> list[TestcaseRecord]:
    bank_override = str(options.bank or "").strip()
    records = select_testcase_inventory(
        services=options.services,
        apis=options.apis,
        testcase_ids=options.testcase_ids,
        banks=[bank_override] if bank_override else None,
        include_disabled=options.include_disabled,
    )
    testcase_key_filter = {
        key.strip().lower()
        for key in options.testcase_keys
        if key and key.strip()
    }
    if testcase_key_filter:
        records = [
            record
            for record in records
            if f"{record.service}::{record.tc_id}".lower() in testcase_key_filter
        ]
    if options.exclude_dqrc:
        records = [record for record in records if record.api_name != "merchant_payment_direct_dqrc"]
    if bank_override:
        records = [replace(record, bank=bank_override) for record in records]
    return records


def _run_job(job_id: str, options: ExecutionOptions) -> None:
    state = get_execution_state(job_id)
    if state is None:
        return

    started = datetime.now()
    state.status = "running"
    state.started_at = started.isoformat(timespec="seconds")
    original_env = {name: os.environ.get(name) for name in ["MAX_WORKERS", "ENABLED_SERVICES"]}
    os.environ["MAX_WORKERS"] = str(max(1, options.workers))
    os.environ["ENABLED_SERVICES"] = ",".join(options.services)

    try:
        runner = SITRunner(ROOT_DIR)
        defaults = runner.api_config.get("defaults", {})
        runner.api_client = ApiClient(
            timeout_seconds=int(options.timeout),
            retries=int(options.retries),
            retry_backoff_factor=float(defaults.get("retry_backoff_factor", 0.5)),
            retry_status_codes=list(defaults.get("retry_status_codes", [500, 502, 503, 504])),
            request_logger=runner.request_logger,
            response_logger=runner.response_logger,
            error_logger=runner.error_logger,
        )
        records = _select_records(options)
        auth_names_by_service = {
            service: set(runner._auth_api_names(service)) for service in {record.service for record in records}
        }
        selected_banks_by_service: dict[str, set[str]] = {}
        for record in records:
            selected_banks_by_service.setdefault(record.service, set()).add(record.bank)
        auth_records = [
            record
            for record in load_testcase_inventory(banks=[options.bank] if str(options.bank or "").strip() else None)
            if record.service in auth_names_by_service and record.api_name in auth_names_by_service[record.service]
            and record.execute == "Y"
            and record.test_type == "positive"
        ]
        bank_scoped_auth_records: list[TestcaseRecord] = []
        for record in auth_records:
            for bank in sorted(selected_banks_by_service.get(record.service, {record.bank})):
                bank_scoped_auth_records.append(replace(record, bank=bank))
        selected_keys = {(record.service, record.tc_id) for record in records}
        ordered_auth_records = [
            record for record in bank_scoped_auth_records if (record.service, record.tc_id) not in selected_keys
        ]
        ordered_records = [*ordered_auth_records, *records]

        state.total = len(ordered_records)
        if not ordered_records:
            state.status = "completed"
            state.finished_at = datetime.now().isoformat(timespec="seconds")
            return

        results: list[dict[str, Any]] = []
        result_lock = threading.Lock()

        def execute(record: TestcaseRecord) -> dict[str, Any]:
            if state.cancel_requested:
                skipped_result = {
                    "tc_id": record.tc_id,
                    "service": record.service,
                    "description": record.description,
                    "bank": record.bank,
                    "api_name": record.api_name,
                    "test_type": record.test_type,
                    "trx_type": record.trx_type,
                    "status": "SKIPPED",
                    "expected": record.expected_result,
                    "actual": "Execution stopped by user",
                    "status_code": None,
                    "response_time_ms": 0,
                    "request_payload": {},
                    "request_headers": {},
                    "response_body": {},
                    "error": "Execution stopped by user",
                }
                with result_lock:
                    results.append(skipped_result)
                    state.completed += 1
                    state.skipped += 1
                return skipped_result
            state.current_api = record.api_name
            state.current_testcase = record.tc_id
            result = runner.execute_testcase(to_runner_testcase(record))
            with result_lock:
                results.append(result)
                state.completed += 1
                if result.get("status") == "PASSED":
                    state.passed += 1
                elif result.get("status") == "SKIPPED":
                    state.skipped += 1
                else:
                    state.failed += 1
                elapsed = time.perf_counter() - started_perf
                state.elapsed_seconds = round(elapsed, 1)
                average = elapsed / state.completed if state.completed else 0
                state.estimated_remaining_seconds = round(average * (state.total - state.completed), 1)
            return result

        started_perf = time.perf_counter()
        for record in ordered_auth_records:
            if state.cancel_requested:
                break
            execute(record)

        execution_records = records
        if state.cancel_requested:
            pass
        elif options.parallel:
            with ThreadPoolExecutor(max_workers=max(1, options.workers)) as executor:
                futures = [executor.submit(execute, record) for record in execution_records]
                for future in as_completed(futures):
                    if state.cancel_requested:
                        for pending in futures:
                            pending.cancel()
                        break
                    future.result()
        else:
            for record in execution_records:
                if state.cancel_requested:
                    break
                execute(record)

        results.sort(key=lambda item: (item.get("service", ""), item.get("tc_id", "")))
        finished = datetime.now()
        summary = runner._build_summary(results)
        run_tag = finished.strftime("%Y%m%d_%H%M%S")
        artifact_tag = runner._build_service_artifact_tag(results)
        runner._write_results_json(run_tag, results, summary, artifact_tag=artifact_tag)
        runner._write_results_csv(run_tag, results, artifact_tag=artifact_tag)
        runner._write_html_report(run_tag, results, summary, started, finished, artifact_tag=artifact_tag)

        state.run_tag = run_tag
        state.report_file = str(runner.reports_dir / runner._artifact_file_name("report", run_tag, "html", artifact_tag))
        state.result_file = str(runner.results_dir / runner._artifact_file_name("results", run_tag, "json", artifact_tag))
        state.status = "stopped" if state.cancel_requested else "completed"
        state.finished_at = finished.isoformat(timespec="seconds")
        append_history(
            {
                "run_tag": run_tag,
                "date": state.finished_at,
                "duration_seconds": round((finished - started).total_seconds(), 1),
                "pass_percent": summary.get("pass_percent", 0.0),
                "total": summary.get("total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "services": sorted({record.service for record in records}),
                "apis": sorted({record.api_name for record in records}),
                "environment": options.environment,
                "report_file": state.report_file,
                "result_file": state.result_file,
            }
        )
    except Exception as exc:
        state.status = "failed"
        state.error = str(exc)
        state.finished_at = datetime.now().isoformat(timespec="seconds")
    finally:
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
