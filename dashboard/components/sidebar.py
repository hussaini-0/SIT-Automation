from __future__ import annotations

import streamlit as st

from services.config_service import load_settings


def render_sidebar() -> None:
    settings = load_settings()
    with st.sidebar:
        st.title("QA Control Center")
        st.caption(f"Environment: {settings.environment}")
        st.page_link("app.py", label="Home")
        st.page_link("pages/Testcases.py", label="Testcases")
        st.page_link("pages/Execute.py", label="Execute")
        st.page_link("pages/Stress.py", label="Stress")
        st.page_link("pages/Swagger.py", label="Swagger Import")
        st.page_link("pages/Reports.py", label="Reports")
        st.page_link("pages/Logs.py", label="Logs")
        st.page_link("pages/Settings.py", label="Settings")
        st.divider()
        st.caption("SIT Automation Framework")
