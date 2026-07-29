from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.sidebar import render_sidebar
from dashboard.pages.Home import render


st.set_page_config(page_title="QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
render()
