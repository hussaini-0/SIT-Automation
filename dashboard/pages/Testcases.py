from __future__ import annotations

import dashboard.bootstrap  # noqa: F401
import streamlit as st

from dashboard.components.sidebar import render_sidebar
from services.config_service import get_services_config
from services.testcase_service import load_testcase_inventory


st.set_page_config(page_title="Testcases - QA Control Center", page_icon="QA", layout="wide")
render_sidebar()

records = load_testcase_inventory()
services = get_services_config()

st.title("Testcases")
st.caption("Browse testcase coverage across services, APIs, modules, banks, and validation expectations.")

service_options = {
    service_id: config.get("display_name", service_id) for service_id, config in sorted(services.items())
}
default_services = sorted({record.service for record in records})

selected_services = st.multiselect(
    "Services",
    options=list(service_options),
    default=default_services,
    format_func=lambda service_id: service_options.get(service_id, service_id),
)

filtered_records = [record for record in records if not selected_services or record.service in selected_services]

filter_cols = st.columns(5)
search_text = filter_cols[0].text_input("Search", placeholder="TC ID, API, description, request file")
selected_test_types = filter_cols[1].multiselect(
    "Test Types",
    sorted({record.test_type for record in filtered_records if record.test_type}),
)
selected_trx_types = filter_cols[2].multiselect(
    "Trx Types",
    sorted({record.trx_type for record in filtered_records if record.trx_type}),
)
execute_filter = filter_cols[3].selectbox("Execute Flag", ["All", "Y only", "N only"], index=0)
selected_banks = filter_cols[4].multiselect(
    "Banks",
    sorted({record.bank for record in filtered_records if record.bank}),
)

facet_cols = st.columns(3)
selected_modules = facet_cols[0].multiselect(
    "Modules",
    sorted({record.module for record in filtered_records if record.module}),
)
selected_apis = facet_cols[1].multiselect(
    "APIs",
    sorted({record.api_name for record in filtered_records if record.api_name}),
)
selected_validation_types = facet_cols[2].multiselect(
    "Validation Types",
    sorted({record.validation_type for record in filtered_records if record.validation_type}),
)

if selected_test_types:
    filtered_records = [record for record in filtered_records if record.test_type in selected_test_types]
if selected_trx_types:
    filtered_records = [record for record in filtered_records if record.trx_type in selected_trx_types]
if selected_banks:
    filtered_records = [record for record in filtered_records if record.bank in selected_banks]
if selected_modules:
    filtered_records = [record for record in filtered_records if record.module in selected_modules]
if selected_apis:
    filtered_records = [record for record in filtered_records if record.api_name in selected_apis]
if selected_validation_types:
    filtered_records = [
        record for record in filtered_records if record.validation_type in selected_validation_types
    ]

if execute_filter == "Y only":
    filtered_records = [record for record in filtered_records if record.execute == "Y"]
elif execute_filter == "N only":
    filtered_records = [record for record in filtered_records if record.execute == "N"]

if search_text.strip():
    search_value = search_text.strip().lower()
    filtered_records = [
        record
        for record in filtered_records
        if search_value in record.tc_id.lower()
        or search_value in record.api_name.lower()
        or search_value in record.description.lower()
        or search_value in record.request_file.lower()
        or search_value in record.expected_result.lower()
    ]

summary_cols = st.columns(6)
summary_cols[0].metric("Matching Rows", len(filtered_records))
summary_cols[1].metric("Services", len({record.service for record in filtered_records}))
summary_cols[2].metric("Modules", len({record.module for record in filtered_records if record.module}))
summary_cols[3].metric("APIs", len({record.api_name for record in filtered_records if record.api_name}))
summary_cols[4].metric("Execute=Y", sum(1 for record in filtered_records if record.execute == "Y"))
summary_cols[5].metric("Negative", sum(1 for record in filtered_records if record.test_type == "negative"))

st.subheader("Testcase Inventory")
st.dataframe(
    [
        {
            "Service": record.service,
            "Service Name": record.service_name,
            "Module": record.module,
            "API": record.api_name,
            "TC ID": record.tc_id,
            "Description": record.description,
            "Type": record.test_type,
            "Trx Type": record.trx_type,
            "Validation": record.validation_type,
            "Execute": record.execute,
            "Bank": record.bank,
            "Request File": record.request_file,
        }
        for record in filtered_records[:1000]
    ],
    use_container_width=True,
    hide_index=True,
)
if len(filtered_records) > 1000:
    st.caption(f"Showing first 1000 rows out of {len(filtered_records)} matches.")

if not filtered_records:
    st.info("No testcases match the current filters.")
    st.stop()

detail_options = {
    f"{record.service} | {record.api_name} | {record.tc_id}": record for record in filtered_records
}
selected_label = st.selectbox("Inspect Testcase", list(detail_options))
selected_record = detail_options[selected_label]

detail_cols = st.columns(2)
with detail_cols[0]:
    st.subheader("Case Details")
    st.json(
        {
            "tc_id": selected_record.tc_id,
            "service": selected_record.service,
            "service_name": selected_record.service_name,
            "module": selected_record.module,
            "api_name": selected_record.api_name,
            "description": selected_record.description,
            "test_type": selected_record.test_type,
            "trx_type": selected_record.trx_type,
            "validation_type": selected_record.validation_type,
            "execute": selected_record.execute,
            "bank": selected_record.bank,
            "request_file": selected_record.request_file,
            "flow_config": selected_record.flow_config,
        }
    )

with detail_cols[1]:
    st.subheader("Expected Outcome")
    st.text_area("Expected Result", value=selected_record.expected_result, height=180, disabled=True)
    st.text_area("Validation Rules", value=selected_record.validation_rules, height=180, disabled=True)
