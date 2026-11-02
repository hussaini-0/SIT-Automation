from __future__ import annotations

import streamlit as st

from dashboard.components.sidebar import render_sidebar
from services.config_service import get_banks_config
from services.sqrc_service import (
    build_sqrc_request_body,
    extract_sqrc_details,
    extract_sqrc_image,
    load_sqrc_profiles,
    load_sqrc_runtime_details,
    save_sqrc_profile,
)


st.set_page_config(page_title="SQRC Data", page_icon="QR", layout="wide")
render_sidebar()

st.title("SQRC Data")
st.caption("Load merchant static-QR data for SQRC testcases.")

banks = get_banks_config() or {}
bank_options = ["Not bank-specific", *sorted(banks)]
selected_bank = st.selectbox("Bank profile", bank_options)
profile_name = st.text_input(
    "SQRC profile name",
    placeholder="Example: Tapsys General Store",
    help="Use a unique name so this QR can be selected later on the Execute page.",
)
uploaded = st.file_uploader(
    "Upload SQRC payload or QR image",
    type=["json", "txt", "payload", "qr", "csv", "png", "jpg", "jpeg", "webp"],
)
text_input = st.text_area("Or paste SQRC contents", height=180, placeholder='{"merchantInfo": {"iban": "...", "bic": "..."}}')

raw = uploaded.getvalue() if uploaded is not None else text_input.encode("utf-8")
source_name = uploaded.name if uploaded is not None else "pasted_sqrc"
is_image = bool(uploaded and uploaded.type.startswith("image/"))
if is_image:
    st.image(raw, caption=source_name, width=700)

if st.button("Extract SQRC", type="secondary", disabled=not raw.strip()):
    try:
        st.session_state["sqrc_extracted"] = (
            extract_sqrc_image(raw, source_name) if is_image else extract_sqrc_details(raw, source_name)
        )
    except Exception as exc:
        st.error(f"SQRC could not be parsed: {exc}")

details = st.session_state.get("sqrc_extracted", {})
if details:
    st.subheader("Extracted values")
    visible = {
        key: value
        for key, value in details.items()
        if key not in {"SQRC_RAW", "SQRC_QR_PAYLOAD", "SQRC_SOURCE_FILE"}
    }
    st.dataframe([{"Field": key, "Value": value} for key, value in visible.items()], hide_index=True, use_container_width=True)
    st.subheader("SQRC request body preview")
    st.json(build_sqrc_request_body(details))
    if st.button("Save SQRC", type="primary"):
        try:
            bank = "" if selected_bank == "Not bank-specific" else selected_bank
            saved_name = profile_name.strip() or details.get("SQRC_SOURCE_FILE", "SQRC")
            save_sqrc_profile(details, saved_name, bank)
            st.success(f"SQRC profile `{saved_name}` saved. Select it on the Execute page before running.")
        except ValueError as exc:
            st.error(str(exc))

profiles = load_sqrc_profiles()
if profiles:
    st.subheader("Saved SQRC profiles")
    st.dataframe(
        [
            {
                "Profile": name,
                "Bank": values.get("SQRC_BANK", "Not bank-specific"),
                "Merchant": values.get("MERCHANT_ACCOUNT_TITLE", ""),
                "BIC": values.get("MERCHANT_BIC", ""),
                "IBAN": values.get("MERCHANT_IBAN", ""),
            }
            for name, values in profiles.items()
        ],
        hide_index=True,
        use_container_width=True,
    )

saved = load_sqrc_runtime_details()
if saved:
    st.subheader("Saved SQRC profile")
    st.json(
        {
            key: value
            for key, value in saved.items()
            if key not in {"SQRC_RAW", "SQRC_QR_PAYLOAD", "SQRC_SOURCE_FILE"}
        }
    )
