from __future__ import annotations

from pathlib import Path

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.report_viewer import render_report
from dashboard.components.sidebar import render_sidebar
from services.report_service import list_stress_reports, list_stress_results, read_result
from services.stress_service import (
    get_stress_execution_state,
    load_stress_scenarios,
    start_stress_execution,
)
from utils.stress_runner import StressOptions


st.set_page_config(page_title="Stress - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
st.title("Stress")
st.caption("Launch isolated stress runs and inspect their dedicated stress artifacts.")

scenarios = load_stress_scenarios()
scenario_options = ["Custom", *sorted(scenarios)]
selected_scenario = st.selectbox("Scenario", scenario_options)
selected_config = scenarios.get(selected_scenario, {}) if selected_scenario != "Custom" else {}

with st.form("stress_controls"):
    services_default = list(selected_config.get("services", ["cas"]))
    apis_default = list(selected_config.get("apis", []))
    testcase_default = list(selected_config.get("testcase_ids", []))
    col1, col2, col3 = st.columns(3)
    services_input = col1.text_input("Services", value=",".join(services_default), help="Comma-separated service IDs.")
    apis_input = col2.text_input("APIs", value=",".join(apis_default), help="Comma-separated API names.")
    testcases_input = col3.text_input(
        "Testcases",
        value=",".join(testcase_default),
        help="Optional comma-separated testcase IDs.",
    )

    numeric_cols = st.columns(4)
    workers = numeric_cols[0].number_input(
        "Workers",
        min_value=1,
        max_value=128,
        value=int(selected_config.get("workers", 8)),
    )
    duration_seconds = numeric_cols[1].number_input(
        "Duration sec",
        min_value=1,
        max_value=3600,
        value=int(selected_config.get("duration_seconds", 60)),
    )
    iterations = numeric_cols[2].number_input(
        "Iterations",
        min_value=0,
        max_value=1_000_000,
        value=int(selected_config.get("iterations", 0)),
        help="Use 0 to run by duration instead.",
    )
    ramp_seconds = numeric_cols[3].number_input(
        "Ramp sec",
        min_value=0,
        max_value=3600,
        value=int(selected_config.get("ramp_seconds", 0)),
    )

    toggle_cols = st.columns(4)
    think_time_ms = toggle_cols[0].number_input(
        "Think Time ms",
        min_value=0,
        max_value=60_000,
        value=int(selected_config.get("think_time_ms", 0)),
    )
    positive_only = toggle_cols[1].toggle(
        "Positive Only",
        value=bool(selected_config.get("positive_only", True)),
    )
    allow_stateful = toggle_cols[2].toggle(
        "Allow Stateful APIs",
        value=bool(selected_config.get("allow_stateful_apis", False)),
        help="Enable with caution for APIs like payment or registration.",
    )
    include_disabled = toggle_cols[3].toggle(
        "Include Disabled",
        value=bool(selected_config.get("include_disabled", False)),
    )

    submitted = st.form_submit_button("Start Stress Run", type="primary")

if submitted:
    services = [item.strip() for item in services_input.split(",") if item.strip()]
    apis = [item.strip() for item in apis_input.split(",") if item.strip()]
    testcase_ids = [item.strip() for item in testcases_input.split(",") if item.strip()]
    options = StressOptions(
        services=services,
        apis=apis,
        testcase_ids=testcase_ids,
        include_disabled=bool(include_disabled),
        workers=int(workers),
        duration_seconds=int(duration_seconds),
        iterations=int(iterations),
        ramp_seconds=int(ramp_seconds),
        think_time_ms=int(think_time_ms),
        positive_only=bool(positive_only),
        allow_stateful_apis=bool(allow_stateful),
        scenario_name="" if selected_scenario == "Custom" else selected_scenario,
    )
    job_id = start_stress_execution(options)
    st.session_state["stress_job_id"] = job_id
    st.success(f"Stress run started: {job_id}")

job_id = st.session_state.get("stress_job_id", "")
if job_id:
    state = get_stress_execution_state(job_id)
    if state:
        st.subheader("Current Stress Run")
        metric_cols = st.columns(6)
        metric_cols[0].metric("Status", state.status.title())
        metric_cols[1].metric("Requests", state.total_requests)
        metric_cols[2].metric("Passed", state.passed)
        metric_cols[3].metric("Failed", state.failed)
        metric_cols[4].metric("RPS", f"{state.requests_per_second:.2f}")
        metric_cols[5].metric("P95 ms", state.p95_ms)
        st.caption(f"Started: `{state.started_at or '-'}`")
        if state.finished_at:
            st.caption(f"Finished: `{state.finished_at}`")
        if state.error:
            st.error(state.error)
        if state.status == "running":
            st.info("Stress run is executing in the background. Use Refresh from the Streamlit toolbar to update progress.")
        if state.report_file:
            st.write(f"Stress report: `{state.report_file}`")
        if state.result_file:
            st.write(f"Stress results: `{state.result_file}`")

st.subheader("Stress Artifacts")
artifacts = list_stress_reports() + list_stress_results()
if not artifacts:
    st.info("No stress reports or result files found yet.")
    st.stop()

selected_name = st.selectbox(
    "Artifact",
    [str(artifact.path) for artifact in artifacts],
    format_func=lambda item: Path(item).name,
)
selected_path = Path(selected_name)
artifact_cols = st.columns([1, 1, 4])
with selected_path.open("rb") as handle:
    artifact_cols[0].download_button("Download", handle, file_name=selected_path.name)
if artifact_cols[1].button("Open Artifact", type="primary"):
    st.session_state["show_stress_artifact"] = True

show_artifact = st.session_state.get("show_stress_artifact", True)
if show_artifact:
    st.subheader("Artifact Viewer")
    render_report(selected_path)

json_artifacts = [artifact for artifact in artifacts if artifact.path.suffix.lower() == ".json"]
if json_artifacts:
    st.subheader("Stress Summary")
    selected_json = st.selectbox(
        "Summary JSON",
        [str(artifact.path) for artifact in json_artifacts],
        format_func=lambda item: Path(item).name,
        key="stress_summary_json",
    )
    data = read_result(Path(selected_json))
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    if summary:
        summary_cols = st.columns(6)
        summary_cols[0].metric("Requests", int(summary.get("total_requests", 0) or 0))
        summary_cols[1].metric("Pass %", f"{float(summary.get('pass_percent', 0.0) or 0.0):.1f}%")
        summary_cols[2].metric("RPS", f"{float(summary.get('requests_per_second', 0.0) or 0.0):.2f}")
        summary_cols[3].metric("P50 ms", int(summary.get("p50_ms", 0) or 0))
        summary_cols[4].metric("P95 ms", int(summary.get("p95_ms", 0) or 0))
        summary_cols[5].metric("P99 ms", int(summary.get("p99_ms", 0) or 0))
        st.dataframe(summary.get("api_breakdown", []), use_container_width=True, hide_index=True)
        top_failures = summary.get("top_failures", [])
        if top_failures:
            st.dataframe(top_failures, use_container_width=True, hide_index=True)
