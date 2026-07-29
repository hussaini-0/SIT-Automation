from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st
from dataclasses import replace

from dashboard.components.execution_progress import render_execution_progress
from dashboard.components.sidebar import render_sidebar
from services.config_service import get_banks_config, get_services_config, load_settings
from services.dqrc_service import extract_dqrc_details, load_runtime_rtp_id, save_dqrc_runtime_details
from services.execution_service import ExecutionOptions, cancel_execution, get_execution_state, start_execution
from services.health_service import check_records_reachability
from services.report_service import latest_result
from services.testcase_validation_service import validate_records_for_run
from services.testcase_service import load_testcase_inventory


st.set_page_config(page_title="Execute - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
settings = load_settings()
records = load_testcase_inventory()
services = get_services_config()
banks = dict(get_banks_config() or {})

st.title("Execute")
st.caption("Select services, APIs, modules, or individual testcases and run them in the background.")

service_options = {
    service_id: config.get("display_name", service_id) for service_id, config in sorted(services.items())
}
default_services = [
    service_id for service_id, config in services.items() if bool(config.get("enabled", True))
]
selected_services = st.multiselect(
    "Services",
    options=list(service_options),
    default=default_services or list(service_options)[:1],
    format_func=lambda service_id: service_options.get(service_id, service_id),
)

bank_options = ["Use Excel Bank values", *sorted(banks)]
selected_bank = st.selectbox(
    "Bank",
    bank_options,
    format_func=lambda bank: (
        bank
        if bank == "Use Excel Bank values"
        else f"{bank} - {banks.get(bank, {}).get('display_name', bank) if isinstance(banks.get(bank), dict) else bank}"
    ),
    help="Choose a bank profile to run the selected testcases against. Leave as Excel values to use each row's Bank column.",
)
bank_override = "" if selected_bank == "Use Excel Bank values" else selected_bank
missing_service_urls: list[str] = []
if bank_override:
    bank_config = banks.get(bank_override, {})
    bank_services = bank_config.get("services", {}) if isinstance(bank_config, dict) else {}
    missing_service_urls = [
        service
        for service in selected_services
        if not str((bank_services.get(service, {}) or {}).get("base_url", "")).strip()
    ]
    if missing_service_urls:
        st.warning(
            f"Bank `{bank_override}` is missing base URLs for: {', '.join(missing_service_urls)}. "
            "Fill them in config/servers.yaml before running this bank."
        )

filtered_records = [record for record in records if record.service in selected_services]
if bank_override:
    filtered_records = [replace(record, bank=bank_override) for record in filtered_records]
latest_failed_testcases = {
    str(item.get("tc_id", "")).strip()
    for item in latest_result().get("results", [])
    if str(item.get("status", "")).upper() != "PASSED" and str(item.get("tc_id", "")).strip()
}

filter_cols = st.columns(4)
search_text = filter_cols[0].text_input("Search", placeholder="TC ID, API, description")
type_filter = filter_cols[1].multiselect(
    "Test Types",
    sorted({record.test_type for record in filtered_records if record.test_type}),
)
execute_filter = filter_cols[2].selectbox("Execute Flag", ["All", "Y only", "N only"], index=1)
failed_only = filter_cols[3].toggle("Latest failed only", value=False)

module_options = sorted({record.module for record in filtered_records if record.module})
selected_modules = st.multiselect("Modules", module_options)
if selected_modules:
    filtered_records = [record for record in filtered_records if record.module in selected_modules]

api_options = sorted({record.api_name for record in filtered_records if record.api_name})
selected_apis = st.multiselect("APIs", api_options)
if selected_apis:
    filtered_records = [record for record in filtered_records if record.api_name in selected_apis]

exclude_dqrc = st.toggle(
    "Exclude DQRC cases",
    value=False,
    help="Turn this on when you have not uploaded a fresh DQRC/RTP ID for this run.",
)
if exclude_dqrc:
    filtered_records = [record for record in filtered_records if record.api_name != "merchant_payment_direct_dqrc"]

st.subheader("DQRC Runtime Data")
dqrc_cols = st.columns([2, 3])
dqrc_upload = dqrc_cols[0].file_uploader(
    "Upload DQRC before running DQRC cases",
    type=["txt", "json", "dqrc", "payload"],
    help="Upload a DQRC text/JSON payload. The dashboard extracts RTP_ID and stores it for this run.",
)
if dqrc_upload is not None:
    try:
        dqrc_details = extract_dqrc_details(dqrc_upload.getvalue(), dqrc_upload.name)
        save_dqrc_runtime_details(dqrc_details)
        st.session_state["dqrc_rtp_id"] = dqrc_details["RTP_ID"]
        dqrc_cols[1].success(f"DQRC RTP ID loaded: {dqrc_details['RTP_ID']}")
    except Exception as exc:
        st.session_state.pop("dqrc_rtp_id", None)
        dqrc_cols[1].error(str(exc))
else:
    existing_rtp_id = st.session_state.get("dqrc_rtp_id") or load_runtime_rtp_id()
    if existing_rtp_id:
        dqrc_cols[1].caption(f"Current runtime RTP ID: `{existing_rtp_id}`")
    else:
        dqrc_cols[1].caption("No DQRC RTP ID loaded.")

if type_filter:
    filtered_records = [record for record in filtered_records if record.test_type in type_filter]

if execute_filter == "Y only":
    filtered_records = [record for record in filtered_records if record.execute == "Y"]
elif execute_filter == "N only":
    filtered_records = [record for record in filtered_records if record.execute == "N"]

if failed_only:
    filtered_records = [record for record in filtered_records if record.tc_id in latest_failed_testcases]

if search_text.strip():
    search_value = search_text.strip().lower()
    filtered_records = [
        record
        for record in filtered_records
        if search_value in record.tc_id.lower()
        or search_value in record.api_name.lower()
        or search_value in record.description.lower()
        or search_value in record.module.lower()
    ]

summary_cols = st.columns(5)
summary_cols[0].metric("Matching Rows", len(filtered_records))
summary_cols[1].metric("Services", len({record.service for record in filtered_records}))
summary_cols[2].metric("APIs", len({record.api_name for record in filtered_records}))
summary_cols[3].metric("Negative", sum(1 for record in filtered_records if record.test_type == "negative"))
summary_cols[4].metric("Execute=Y", sum(1 for record in filtered_records if record.execute == "Y"))

testcase_labels = {
    f"{record.service} | {record.api_name} | {record.tc_id} | {record.description[:80]}": f"{record.service}::{record.tc_id}"
    for record in filtered_records
}
selected_testcase_labels = st.multiselect(
    "Testcases",
    list(testcase_labels),
    help="Leave empty to run the full filtered selection.",
)
selected_testcase_keys = [testcase_labels[label] for label in selected_testcase_labels]
filtered_testcase_keys = [f"{record.service}::{record.tc_id}" for record in filtered_records]
execution_testcase_keys = selected_testcase_keys or filtered_testcase_keys

selection_note = (
    f"Running {len(selected_testcase_keys)} explicitly selected testcase(s)."
    if selected_testcase_keys
    else f"Running all {len(filtered_records)} filtered testcase(s)."
)
st.caption(selection_note)

st.subheader("Selected Inventory")
st.dataframe(
    [
        {
            "Service": record.service,
            "Bank": record.bank,
            "Module": record.module,
            "API": record.api_name,
            "TC ID": record.tc_id,
            "Type": record.test_type,
            "Trx Type": record.trx_type,
            "Execute Flag": record.execute,
            "Description": record.description,
        }
        for record in filtered_records[:500]
    ],
    use_container_width=True,
    hide_index=True,
)
if len(filtered_records) > 500:
    st.caption(f"Showing first 500 rows out of {len(filtered_records)} matches.")

with st.form("execution_controls"):
    st.subheader("Execution Controls")
    cols = st.columns(6)
    workers = cols[0].number_input("Workers", min_value=1, max_value=64, value=settings.default_workers)
    retries = cols[1].number_input("Retries", min_value=0, max_value=10, value=settings.default_retries)
    timeout = cols[2].number_input("Timeout sec", min_value=1, max_value=600, value=settings.default_timeout)
    parallel = cols[3].toggle("Parallel", value=True)
    verbose = cols[4].toggle("Verbose", value=settings.verbose_logging)
    environment = cols[5].text_input("Environment", value=settings.environment)
    include_disabled = st.toggle("Include Excel rows marked Execute=N", value=False)
    pre_run_checks = st.toggle(
        "Pre-run checks",
        value=True,
        help="Validate request files/placeholders and quickly check selected service ports before running.",
    )
    submitted = st.form_submit_button("Run Selection", type="primary")

if submitted:
    execution_testcase_key_set = set(execution_testcase_keys)
    runnable_records = [
        record
        for record in filtered_records
        if f"{record.service}::{record.tc_id}" in execution_testcase_key_set
    ]
    selected_has_dqrc = any(record.api_name == "merchant_payment_direct_dqrc" for record in runnable_records)
    has_runtime_rtp_id = bool(st.session_state.get("dqrc_rtp_id"))
    if not selected_services:
        st.warning("Select at least one service.")
    elif not filtered_records:
        st.warning("No testcases match the current filters.")
    elif missing_service_urls:
        st.warning(
            f"Bank `{bank_override}` is missing base URLs for: {', '.join(missing_service_urls)}. "
            "Update config/servers.yaml before running."
        )
    elif selected_has_dqrc and not has_runtime_rtp_id:
        st.warning("Upload DQRC first. DQRC cases need a fresh RTP ID before execution.")
    else:
        if pre_run_checks:
            validation_issues = validate_records_for_run(runnable_records)
            blocking_issues = [issue for issue in validation_issues if issue.severity == "error"]
            if blocking_issues:
                st.error("Pre-run validation failed. Fix these before starting execution.")
                st.dataframe(
                    [
                        {
                            "TC ID": issue.tc_id,
                            "Service": issue.service,
                            "Bank": issue.bank,
                            "API": issue.api_name,
                            "Issue": issue.message,
                        }
                        for issue in blocking_issues[:50]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                st.stop()

            reachability_results = check_records_reachability(
                runnable_records,
                timeout_seconds=min(5, int(timeout)),
            )
            unreachable = [result for result in reachability_results if not result.reachable]
            if unreachable:
                st.error("Pre-run connectivity failed. Check VPN/base URLs before starting execution.")
                st.dataframe(
                    [
                        {
                            "Service": result.service,
                            "Bank": result.bank,
                            "Base URL": result.base_url,
                            "Issue": result.error,
                        }
                        for result in unreachable
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                st.stop()

        job_id = start_execution(
            ExecutionOptions(
                services=selected_services,
                apis=selected_apis,
                testcase_keys=execution_testcase_keys,
                bank=bank_override,
                workers=int(workers),
                timeout=int(timeout),
                retries=int(retries),
                parallel=bool(parallel),
                environment=environment,
                verbose_logging=bool(verbose),
                include_disabled=bool(include_disabled),
                exclude_dqrc=bool(exclude_dqrc),
            )
        )
        st.session_state["execution_job_id"] = job_id
        if selected_has_dqrc:
            st.session_state.pop("dqrc_rtp_id", None)
        st.success(f"Execution started: {job_id}")

job_id = st.session_state.get("execution_job_id")
if job_id:
    state = get_execution_state(job_id)
    if state:
        st.subheader("Execution Progress")
        render_execution_progress(state)
        if state.status in {"running", "stopping"}:
            st.info("Execution is running in the background. Refreshing keeps the UI responsive.")
            progress_cols = st.columns([1, 1, 5])
            progress_cols[0].button("Refresh Progress")
            stop_disabled = state.status == "stopping"
            if progress_cols[1].button("Stop Execution", type="secondary", disabled=stop_disabled):
                if cancel_execution(job_id):
                    st.warning("Stop requested. Running API calls may finish, but no new testcases will be started.")
                    st.rerun()
                else:
                    st.info("This execution is no longer running.")
            if state.status == "stopping":
                st.warning("Stopping execution. Waiting for in-flight requests to finish.")
        elif state.status == "completed":
            st.success(f"Completed run `{state.run_tag}`")
            st.write(f"Report: `{state.report_file}`")
            st.write(f"Results: `{state.result_file}`")
            st.page_link("pages/Reports.py", label="Review Report")
        elif state.status == "stopped":
            st.warning(f"Stopped run `{state.run_tag}`")
            st.write(f"Report: `{state.report_file}`")
            st.write(f"Results: `{state.result_file}`")
            st.page_link("pages/Reports.py", label="Review Partial Report")
        elif state.status == "failed":
            st.error(state.error or "Execution failed.")
