from __future__ import annotations

import streamlit as st

from services.execution_service import ExecutionState


def render_execution_progress(state: ExecutionState) -> None:
    st.progress(min(state.percent / 100, 1.0), text=f"{state.percent}%")
    cols = st.columns(6)
    cols[0].metric("Total", state.total)
    cols[1].metric("Passed", state.passed)
    cols[2].metric("Failed", state.failed)
    cols[3].metric("Skipped", state.skipped)
    cols[4].metric("Elapsed", f"{state.elapsed_seconds:.1f}s")
    cols[5].metric("Remaining", f"{state.estimated_remaining_seconds:.1f}s")
    st.write(f"Current API: `{state.current_api or '-'}`")
    st.write(f"Current Testcase: `{state.current_testcase or '-'}`")
    if state.error:
        st.error(state.error)
