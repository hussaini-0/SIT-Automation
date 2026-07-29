from __future__ import annotations

from pathlib import Path

import streamlit as st

from services.report_service import read_text


def render_log_viewer(path: Path, search: str = "") -> None:
    text = read_text(path)
    lines = text.splitlines()
    if search:
        needle = search.lower()
        lines = [line for line in lines if needle in line.lower()]
    st.code("\n".join(lines[-1000:]) or "No log entries matched.", language="text")
