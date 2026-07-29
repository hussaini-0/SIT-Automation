from __future__ import annotations

from pathlib import Path

import streamlit as st

from services.report_service import read_result, read_text


def render_report(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".html":
        st.components.v1.html(read_text(path, max_chars=None), height=760, scrolling=True)
    elif suffix == ".json":
        st.json(read_result(path))
    else:
        st.code(read_text(path), language="text")
