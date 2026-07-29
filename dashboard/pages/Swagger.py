from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.sidebar import render_sidebar
from services.config_service import ensure_service, get_services_config, normalize_service_id
from services.swagger_service import import_openapi_spec, load_spec_from_bytes, load_spec_from_url


st.set_page_config(page_title="Swagger Import - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()
st.title("Swagger Import")

services = get_services_config()
target_mode = st.radio("Target", ["Existing Service", "New Service"], horizontal=True)

if target_mode == "Existing Service":
    service_id = st.selectbox(
        "Target Service",
        sorted(services),
        format_func=lambda item: services[item].get("display_name", item),
    )
else:
    cols = st.columns([1, 1, 2])
    new_service_name = cols[0].text_input("Service Name", placeholder="Bulk Sending")
    new_service_id = cols[1].text_input(
        "Service ID",
        value=normalize_service_id(new_service_name) if new_service_name else "",
        placeholder="bulk_sending",
    )
    new_base_url = cols[2].text_input("Base URL", placeholder="http://10.0.150.36:8007")
    service_id = new_service_id

url = st.text_input(
    "Swagger/OpenAPI JSON URL",
    help="Use the raw spec endpoint, not the Swagger UI page. Common paths are /v3/api-docs, /openapi.json, or /swagger.json.",
)
uploaded = st.file_uploader("Upload Swagger/OpenAPI JSON or YAML", type=["json", "yaml", "yml"])
if uploaded:
    st.success(f"Selected spec file: {uploaded.name}")

if st.button("Import", type="primary"):
    try:
        if target_mode == "New Service":
            service_id = ensure_service(
                service_id=service_id,
                display_name=new_service_name,
                base_url=new_base_url,
                enabled=False,
            )
        spec = load_spec_from_url(url) if url else load_spec_from_bytes(uploaded.getvalue()) if uploaded else None
        if spec is None:
            st.warning("Provide a Swagger/OpenAPI JSON URL or upload a JSON/YAML spec file.")
        else:
            summary = import_openapi_spec(spec, service_id)
            cols = st.columns(4)
            cols[0].metric("Imported", summary.imported)
            cols[1].metric("Skipped", summary.skipped)
            cols[2].metric("Modified", summary.modified)
            cols[3].metric("Errors", len(summary.errors))
            st.success(f"Import completed for `{service_id}`.")
            if summary.errors:
                st.error("\n".join(summary.errors))
            st.write(f"Import report: `{summary.report_file}`")
    except Exception as exc:
        st.error(str(exc))
