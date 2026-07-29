from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.log_viewer import render_log_viewer
from dashboard.components.sidebar import render_sidebar
from services.report_service import available_logs


st.set_page_config(page_title="Logs - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
st.title("Logs")

logs = available_logs()
if not logs:
    st.info("No logs found.")
    st.stop()

selected = st.selectbox("Log", logs, format_func=lambda path: path.name)
cols = st.columns([3, 1])
search = cols[0].text_input("Search")
auto_refresh = cols[1].toggle("Auto Refresh", value=False)
if auto_refresh:
    st.caption("Use Refresh from the Streamlit toolbar to reload the latest log entries.")

render_log_viewer(selected, search)
