from __future__ import annotations

import json
from pathlib import Path

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.report_viewer import render_report
from dashboard.components.sidebar import render_sidebar
from services.report_service import list_reports, list_results, read_result


st.set_page_config(page_title="Reports - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
st.title("Reports")

artifacts = list_reports() + list_results()
if not artifacts:
    st.info("No reports or result files found.")
    st.stop()

selected_name = st.selectbox(
    "Artifact",
    [str(artifact.path) for artifact in artifacts],
    format_func=lambda item: Path(item).name,
)
selected_path = Path(selected_name)
artifact_cols = st.columns([1, 1, 5])
with selected_path.open("rb") as handle:
    artifact_cols[0].download_button("Download", handle, file_name=selected_path.name)
if artifact_cols[1].button("Review Report", type="primary"):
    st.session_state["show_report_review"] = True

st.subheader("Artifact Viewer")
render_report(selected_path)

show_review = st.session_state.get("show_report_review", True)
if not show_review:
    st.info("Click Review Report to inspect failed/passed testcase details.")
    st.stop()

st.subheader("Report Review")
json_results = [artifact for artifact in artifacts if artifact.path.suffix.lower() == ".json"]
if json_results:
    result_path = st.selectbox(
        "Result JSON",
        [str(artifact.path) for artifact in json_results],
        format_func=lambda item: Path(item).name,
    )
    data = read_result(Path(result_path))
    result_rows = data.get("results", [])
    summary = data.get("summary", {})

    metrics = st.columns(5)
    metrics[0].metric("Total", int(summary.get("total", len(result_rows)) or len(result_rows)))
    metrics[1].metric("Passed", int(summary.get("passed", 0) or 0))
    metrics[2].metric("Failed", int(summary.get("failed", 0) or 0))
    metrics[3].metric("Pass %", f"{float(summary.get('pass_percent', 0.0) or 0.0):.1f}%")
    metrics[4].metric("Run Tag", str(data.get("run_tag", "") or "-"))
    st.caption(
        "Expected negative passes: "
        f"{int(summary.get('expected_negative_passed', 0) or 0)} | "
        "Regression failed: "
        f"{int(summary.get('regression_failed', 0) or 0)} | "
        "Negative mismatch: "
        f"{int(summary.get('negative_mismatch', 0) or 0)}"
    )

    filter_cols = st.columns(5)
    status_filter = filter_cols[0].selectbox("Status", ["Failed only", "All", "Passed only"])
    service_filter = filter_cols[1].multiselect(
        "Service",
        sorted({str(row.get("service", "")) for row in result_rows if row.get("service")}),
    )
    api_filter = filter_cols[2].multiselect(
        "API",
        sorted({str(row.get("api_name", "")) for row in result_rows if row.get("api_name")}),
    )
    type_filter = filter_cols[3].multiselect(
        "Test Type",
        sorted({str(row.get("test_type", "")) for row in result_rows if row.get("test_type")}),
    )
    search_text = filter_cols[4].text_input("Search", placeholder="TC ID or text")

    filtered_rows = result_rows
    if status_filter == "Failed only":
        filtered_rows = [row for row in filtered_rows if str(row.get("status", "")).upper() != "PASSED"]
    elif status_filter == "Passed only":
        filtered_rows = [row for row in filtered_rows if str(row.get("status", "")).upper() == "PASSED"]

    if service_filter:
        filtered_rows = [row for row in filtered_rows if row.get("service") in service_filter]
    if api_filter:
        filtered_rows = [row for row in filtered_rows if row.get("api_name") in api_filter]
    if type_filter:
        filtered_rows = [row for row in filtered_rows if row.get("test_type") in type_filter]
    if search_text.strip():
        search_value = search_text.strip().lower()
        filtered_rows = [
            row
            for row in filtered_rows
            if search_value in str(row.get("tc_id", "")).lower()
            or search_value in str(row.get("api_name", "")).lower()
            or search_value in str(row.get("description", "")).lower()
            or search_value in str(row.get("actual", "")).lower()
        ]

    st.caption(f"{len(filtered_rows)} testcase(s) match the current report filters.")
    st.dataframe(
        [
            {
                "TC ID": row.get("tc_id", ""),
                "Service": row.get("service", ""),
                "API": row.get("api_name", ""),
                "Status": row.get("status", ""),
                "Outcome": (
                    "Expected Negative"
                    if str(row.get("test_type", "")).lower() == "negative" and str(row.get("status", "")).upper() == "PASSED"
                    else "Negative Mismatch"
                    if str(row.get("test_type", "")).lower() == "negative"
                    else "Positive Pass"
                    if str(row.get("status", "")).upper() == "PASSED"
                    else "Regression"
                ),
                "Type": row.get("test_type", ""),
                "Response ms": row.get("response_time_ms", 0),
                "Expected": row.get("expected", ""),
                "Actual": str(row.get("actual", ""))[:120],
            }
            for row in filtered_rows[:300]
        ],
        use_container_width=True,
        hide_index=True,
    )
    if len(filtered_rows) > 300:
        st.caption(f"Showing first 300 rows out of {len(filtered_rows)} matches.")

    choice = (
        st.selectbox(
            "Inspect testcase",
            filtered_rows,
            format_func=lambda row: f"{row.get('status')} | {row.get('service')} | {row.get('api_name')} | {row.get('tc_id')}",
        )
        if filtered_rows
        else None
    )
    if choice:
        compare_cols = st.columns(2)
        compare_cols[0].text_area("Expected", str(choice.get("expected", "")), height=120)
        compare_cols[1].text_area("Actual", str(choice.get("actual", "")), height=120)

        tabs = st.tabs(["Request", "Response", "Headers", "Validation", "Logs"])
        tabs[0].json(choice.get("request_payload", {}))
        tabs[1].json(choice.get("response_body", {}))
        tabs[2].json(choice.get("request_headers", {}))
        tabs[3].json(
            {
                "status": choice.get("status", ""),
                "status_code": choice.get("status_code"),
                "response_time_ms": choice.get("response_time_ms"),
                "error": choice.get("error", ""),
            }
        )
        tabs[4].code(json.dumps(choice, ensure_ascii=False, indent=2), language="json")
