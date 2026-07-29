from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.sidebar import render_sidebar
from services.config_service import DashboardSettings, get_services_config, load_settings, save_settings, update_service_enabled


st.set_page_config(page_title="Settings - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
st.title("Settings")

settings = load_settings()
with st.form("settings"):
    environment = st.text_input("Environment", value=settings.environment)
    cols = st.columns(4)
    workers = cols[0].number_input("Default Workers", min_value=1, max_value=64, value=settings.default_workers)
    timeout = cols[1].number_input("Default Timeout", min_value=1, max_value=600, value=settings.default_timeout)
    retries = cols[2].number_input("Default Retries", min_value=0, max_value=10, value=settings.default_retries)
    verbose = cols[3].toggle("Verbose Logging", value=settings.verbose_logging)
    report_location = st.text_input("Default Report Location", value=settings.default_report_location)
    result_location = st.text_input("Default Result Location", value=settings.default_result_location)
    submitted = st.form_submit_button("Save Settings", type="primary")

if submitted:
    save_settings(
        DashboardSettings(
            environment=environment,
            default_workers=int(workers),
            default_timeout=int(timeout),
            default_retries=int(retries),
            default_report_location=report_location,
            default_result_location=result_location,
            verbose_logging=bool(verbose),
        )
    )
    st.success("Settings saved.")

st.subheader("Service Defaults")
for service_id, config in sorted(get_services_config().items()):
    enabled = st.toggle(
        config.get("display_name", service_id),
        value=bool(config.get("enabled", True)),
        key=f"enabled_{service_id}",
    )
    if enabled != bool(config.get("enabled", True)):
        update_service_enabled(service_id, enabled)
        st.success(f"Updated {service_id}.")
