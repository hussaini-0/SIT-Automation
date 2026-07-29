from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.sidebar import render_sidebar
from services.config_service import get_services_config, load_settings
from services.report_service import list_reports, load_history, summarize_latest
from services.testcase_service import inventory_summary


def render() -> None:
    settings = load_settings()
    summary = inventory_summary()
    latest = summarize_latest()
    services = get_services_config()

    st.title("QA Control Center")
    st.caption("Operational dashboard for SIT automation execution, reports, logs, and imports.")

    cols = st.columns(4)
    cols[0].metric("Services", summary["services"])
    cols[1].metric("APIs", summary["apis"])
    cols[2].metric("Testcases", f"{summary['testcases']:,}")
    cols[3].metric("Last Pass", f"{latest['pass_percent']:.1f}%")

    status_cols = st.columns(4)
    status_cols[0].metric("Framework Status", "Ready")
    status_cols[1].metric("Environment", settings.environment)
    status_cols[2].metric("Last Execution", latest["last_execution"] or "None")
    status_cols[3].metric("Latest Report", latest["latest_report"] or "None")

    st.subheader("Configured Services")
    st.dataframe(
        [
            {
                "Service": service_id,
                "Name": config.get("display_name", service_id),
                "Status": "Enabled" if bool(config.get("enabled", True)) else "Disabled",
                "Base URL": config.get("base_url", ""),
                "APIs": len(config.get("apis", {}) or {}),
            }
            for service_id, config in sorted(services.items())
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Execution History")
    history = load_history()
    if history:
        st.dataframe(history[:20], use_container_width=True, hide_index=True)
    else:
        st.info("No dashboard executions have been recorded yet.")

    st.subheader("Recent Reports")
    reports = list_reports()[:5]
    if reports:
        for report in reports:
            st.write(f"`{report.path.name}` - {report.modified_at:%Y-%m-%d %H:%M:%S}")
    else:
        st.info("No reports found.")


if __name__ == "__main__":
    st.set_page_config(page_title="QA Control Center", page_icon="QA", layout="wide")
    render_sidebar()
    render()
