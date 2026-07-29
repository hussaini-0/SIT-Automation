from __future__ import annotations

import copy
import json
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runner import SITRunner


DEFAULT_STATEFUL_APIS = {
    "payment",
    "payment1",
    "directposting",
    "remittancepayment",
    "remittancedirectposting",
    "registercustomer",
    "registercaa",
    "updatestatus",
    "modify",
    "alias",
    "modifyalias",
    "delinkaccount",
    "linkaccount",
    "deleteaccount",
    "deletecustomer",
    "onestep",
}


@dataclass
class StressOptions:
    services: list[str]
    apis: list[str]
    testcase_ids: list[str]
    include_disabled: bool = False
    workers: int = 8
    duration_seconds: int = 60
    iterations: int = 0
    ramp_seconds: int = 0
    think_time_ms: int = 0
    positive_only: bool = True
    allow_stateful_apis: bool = False
    scenario_name: str = ""


def load_stress_options(config_dir: Path, args: Any) -> StressOptions:
    config_file = config_dir / "stress.yaml"
    config = {}
    if config_file.exists():
        import yaml

        with config_file.open("r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}

    defaults = config.get("defaults", {}) if isinstance(config, dict) else {}
    scenarios = config.get("scenarios", {}) if isinstance(config, dict) else {}
    scenario_name = str(getattr(args, "stress_scenario", "") or "").strip()
    scenario = scenarios.get(scenario_name, {}) if scenario_name and isinstance(scenarios, dict) else {}

    def pick(name: str, fallback: Any) -> Any:
        value = getattr(args, name, None)
        if value not in (None, "", []):
            return value
        if name in scenario:
            return scenario[name]
        return defaults.get(name, fallback)

    services = list(getattr(args, "services", []) or scenario.get("services", []) or defaults.get("services", []))
    apis = list(getattr(args, "apis", []) or scenario.get("apis", []) or defaults.get("apis", []))
    testcase_ids = list(
        getattr(args, "testcase_ids", []) or scenario.get("testcase_ids", []) or defaults.get("testcase_ids", [])
    )

    return StressOptions(
        services=services,
        apis=apis,
        testcase_ids=testcase_ids,
        include_disabled=bool(getattr(args, "include_disabled", False) or pick("include_disabled", False)),
        workers=max(1, int(pick("workers", 8))),
        duration_seconds=max(1, int(pick("duration_seconds", 60))),
        iterations=max(0, int(pick("iterations", 0))),
        ramp_seconds=max(0, int(pick("ramp_seconds", 0))),
        think_time_ms=max(0, int(pick("think_time_ms", 0))),
        positive_only=bool(pick("positive_only", True)),
        allow_stateful_apis=bool(getattr(args, "allow_stateful_apis", False) or pick("allow_stateful_apis", False)),
        scenario_name=scenario_name,
    )


def run_stress(runner: "SITRunner", options: StressOptions) -> dict[str, Any]:
    started_at = datetime.now()
    run_tag = started_at.strftime("%Y%m%d_%H%M%S")

    testcases = runner.load_testcases(
        services=options.services or None,
        apis=options.apis or None,
        testcase_ids=options.testcase_ids or None,
        include_disabled=options.include_disabled,
    )
    testcases = _filter_stress_testcases(testcases, options)
    if not testcases:
        raise ValueError("No eligible testcases found for stress mode. Adjust filters or stress.yaml.")

    _bootstrap_auth_tokens(runner, testcases)

    results: list[dict[str, Any]] = []
    result_lock = threading.Lock()
    request_counter = 0
    testcase_index = 0
    stop_at = time.perf_counter() + options.duration_seconds
    max_iterations = options.iterations if options.iterations > 0 else None
    total_scheduled = 0

    def execute_once(selected_testcase: Any, sequence_number: int) -> dict[str, Any]:
        started = time.perf_counter()
        result = runner.execute_testcase(copy.deepcopy(selected_testcase))
        duration_ms = int((time.perf_counter() - started) * 1000)
        result["stress_sequence"] = sequence_number
        result["stress_elapsed_ms"] = duration_ms
        result["stress_started_at"] = datetime.now().isoformat(timespec="seconds")
        return result

    futures = {}
    with ThreadPoolExecutor(max_workers=options.workers) as executor:
        while True:
            while len(futures) < options.workers:
                if max_iterations is not None and total_scheduled >= max_iterations:
                    break
                if max_iterations is None and time.perf_counter() >= stop_at:
                    break

                testcase = copy.deepcopy(testcases[testcase_index % len(testcases)])
                testcase_index += 1
                request_counter += 1
                total_scheduled += 1
                future = executor.submit(execute_once, testcase, request_counter)
                futures[future] = testcase
                _sleep_for_ramp(options, started_at, total_scheduled)

            if not futures:
                break

            done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
            for future in done:
                result = future.result()
                futures.pop(future, None)
                with result_lock:
                    results.append(result)
                if options.think_time_ms > 0:
                    time.sleep(options.think_time_ms / 1000)

            if max_iterations is not None and total_scheduled >= max_iterations and not futures:
                break
            if max_iterations is None and time.perf_counter() >= stop_at and not futures:
                break

    finished_at = datetime.now()
    summary = _build_stress_summary(results, started_at, finished_at, options)
    output = {
        "run_tag": run_tag,
        "mode": "stress",
        "scenario": options.scenario_name,
        "options": {
            "services": options.services,
            "apis": options.apis,
            "testcase_ids": options.testcase_ids,
            "workers": options.workers,
            "duration_seconds": options.duration_seconds,
            "iterations": options.iterations,
            "ramp_seconds": options.ramp_seconds,
            "think_time_ms": options.think_time_ms,
            "positive_only": options.positive_only,
            "allow_stateful_apis": options.allow_stateful_apis,
        },
        "summary": summary,
        "results": results,
    }
    _write_stress_outputs(runner, run_tag, output, summary)
    runner.framework_logger.info("Stress execution completed. Summary=%s", summary)
    return output


def _filter_stress_testcases(testcases: list[Any], options: StressOptions) -> list[Any]:
    filtered = list(testcases)
    if options.positive_only:
        filtered = [tc for tc in filtered if str(tc.test_type).strip().lower() == "positive"]
    if not options.allow_stateful_apis:
        filtered = [tc for tc in filtered if str(tc.api_name).strip().lower() not in DEFAULT_STATEFUL_APIS]
    return filtered


def _bootstrap_auth_tokens(runner: "SITRunner", testcases: list[Any]) -> None:
    grouped: dict[str, list[Any]] = {}
    for testcase in testcases:
        grouped.setdefault(testcase.service, []).append(testcase)

    for service, service_testcases in grouped.items():
        auth_api_names = runner._auth_api_names(service)
        non_auth = [tc for tc in service_testcases if tc.api_name not in auth_api_names]
        auth_cases = [tc for tc in service_testcases if tc.api_name in auth_api_names]
        auth_cases.sort(key=lambda tc: runner._tc_order_key(tc.tc_id))
        for auth_tc in auth_cases:
            runner.execute_testcase(copy.deepcopy(auth_tc), capture_auth_token=True, force_auth_token=True)
        if non_auth:
            runner._bootstrap_reusable_auth_tokens(service, auth_api_names, non_auth)


def _sleep_for_ramp(options: StressOptions, started_at: datetime, scheduled_count: int) -> None:
    if options.ramp_seconds <= 0 or options.workers <= 1:
        return
    phase_interval = options.ramp_seconds / max(options.workers - 1, 1)
    elapsed = (datetime.now() - started_at).total_seconds()
    target_elapsed = min((scheduled_count - 1) * phase_interval, options.ramp_seconds)
    if target_elapsed > elapsed:
        time.sleep(target_elapsed - elapsed)


def _build_stress_summary(
    results: list[dict[str, Any]],
    started_at: datetime,
    finished_at: datetime,
    options: StressOptions,
) -> dict[str, Any]:
    latencies = sorted(
        int(result.get("response_time_ms") or result.get("stress_elapsed_ms") or 0)
        for result in results
        if (result.get("response_time_ms") or result.get("stress_elapsed_ms")) is not None
    )
    passed = sum(1 for result in results if result.get("status") == "PASSED")
    failed = sum(1 for result in results if result.get("status") != "PASSED")
    duration_seconds = max((finished_at - started_at).total_seconds(), 0.001)
    failures = Counter()
    api_breakdown = Counter()
    for result in results:
        api_breakdown[f"{result.get('service', '')}/{result.get('api_name', '')}"] += 1
        if result.get("status") != "PASSED":
            failure_key = str(result.get("error") or result.get("actual") or result.get("status_code") or "FAILED")
            failures[failure_key[:160]] += 1
    return {
        "total_requests": len(results),
        "passed": passed,
        "failed": failed,
        "pass_percent": round((passed / len(results)) * 100, 2) if results else 0.0,
        "duration_seconds": round(duration_seconds, 2),
        "requests_per_second": round(len(results) / duration_seconds, 2),
        "workers": options.workers,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
        "p99_ms": _percentile(latencies, 99),
        "max_ms": latencies[-1] if latencies else 0,
        "top_failures": [{"reason": reason, "count": count} for reason, count in failures.most_common(10)],
        "api_breakdown": [{"api": api, "count": count} for api, count in api_breakdown.most_common()],
    }


def _percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    index = round(((percentile / 100) * (len(values) - 1)))
    return int(values[index])


def _write_stress_outputs(runner: "SITRunner", run_tag: str, output: dict[str, Any], summary: dict[str, Any]) -> None:
    stress_results_dir = runner.results_dir / "stress"
    stress_reports_dir = runner.reports_dir / "stress"
    stress_results_dir.mkdir(parents=True, exist_ok=True)
    stress_reports_dir.mkdir(parents=True, exist_ok=True)

    scenario_name = str(output.get("scenario", "") or "").strip()
    service_tag = runner._build_service_artifact_tag(output.get("results", []))
    extra_tag = "-".join(part for part in [runner._slugify_label(scenario_name) if scenario_name else "", service_tag] if part)
    json_path = stress_results_dir / runner._artifact_file_name("stress_results", run_tag, "json", extra_tag)
    csv_path = stress_results_dir / runner._artifact_file_name("stress_results", run_tag, "csv", extra_tag)
    html_path = stress_reports_dir / runner._artifact_file_name("stress_report", run_tag, "html", extra_tag)

    runner._atomic_write_text(json_path, json.dumps(output, ensure_ascii=False, indent=2))

    lines = [
        "sequence,service,api_name,tc_id,status,status_code,response_time_ms,error",
    ]
    for item in output.get("results", []):
        lines.append(
            ",".join(
                [
                    str(item.get("stress_sequence", "")),
                    _csv(item.get("service", "")),
                    _csv(item.get("api_name", "")),
                    _csv(item.get("tc_id", "")),
                    _csv(item.get("status", "")),
                    _csv(item.get("status_code", "")),
                    _csv(item.get("response_time_ms", item.get("stress_elapsed_ms", ""))),
                    _csv(item.get("error", "") or item.get("actual", "")),
                ]
            )
        )
    runner._atomic_write_text(csv_path, "\n".join(lines))

    summary_cards = "".join(
        f"<div class='card'><h3>{_html_escape(str(key).replace('_', ' ').title())}</h3>"
        f"<p>{_html_escape(str(value))}</p></div>"
        for key, value in summary.items()
        if key not in {"top_failures", "api_breakdown"}
    )
    failure_rows = "".join(
        f"<tr><td>{_html_escape(str(item.get('reason', '')))}</td><td>{item.get('count', 0)}</td></tr>"
        for item in summary.get("top_failures", [])
    )
    api_rows = "".join(
        f"<tr><td>{_html_escape(str(item.get('api', '')))}</td><td>{item.get('count', 0)}</td></tr>"
        for item in summary.get("api_breakdown", [])
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stress Report {run_tag}</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; background: #f6f7fb; color: #18202a; margin: 0; padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .card {{ background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }}
    h1, h2 {{ margin: 0 0 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #e5e7ef; text-align: left; vertical-align: top; }}
    th {{ background: #eef2ff; }}
    section {{ margin-bottom: 24px; }}
  </style>
</head>
<body>
  <h1>Stress Report</h1>
  <p>Run tag: {_html_escape(run_tag)}</p>
  <section>
    <div class="grid">{summary_cards}</div>
  </section>
  <section>
    <h2>Top Failures</h2>
    <table><thead><tr><th>Reason</th><th>Count</th></tr></thead><tbody>{failure_rows}</tbody></table>
  </section>
  <section>
    <h2>API Breakdown</h2>
    <table><thead><tr><th>API</th><th>Count</th></tr></thead><tbody>{api_rows}</tbody></table>
  </section>
</body>
</html>
"""
    runner._atomic_write_text(html_path, html)


def _csv(value: Any) -> str:
    text = str(value if value is not None else "")
    return '"' + text.replace('"', '""') + '"'


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
