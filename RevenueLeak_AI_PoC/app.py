from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from revenueleak import (
    REQUIRED_COLUMNS, create_demo_data, run_agentic_workflow, validate_upload,
    build_case_report_csv,
)

st.set_page_config(page_title="RevenueLeak AI", page_icon="💸", layout="wide")

st.markdown("""
<style>
    .stApp { background: #0b1020; color: #edf2f7; }
    [data-testid="stSidebar"] { background: #111a2e; }
    .hero { padding: 1.2rem 1.4rem; border: 1px solid #2b3a57; border-radius: 16px;
            background: linear-gradient(120deg,#14233d,#111827); margin-bottom: 1rem; }
    .hero h1 { margin: 0; color: #f8fafc; letter-spacing: .02em; }
    .hero p { color: #b9c6d8; margin: .35rem 0 0; }
    .small-note { color: #9fb0c8; font-size: .88rem; }
    div[data-testid="stMetric"] { background: #121d31; border: 1px solid #273751;
        padding: 12px; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

if "results" not in st.session_state:
    st.session_state.results = None
if "input_data" not in st.session_state:
    st.session_state.input_data = None

st.markdown("""
<div class="hero">
  <h1>💸 RevenueLeak AI</h1>
  <p>Agentic marketplace settlement reconciliation · synthetic-data proof of concept</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Control panel")
    st.caption("Use the built-in demo data or upload your own CSV files.")
    source = st.radio("Input source", ["Built-in demo data", "Upload CSV files"])
    st.divider()
    st.markdown("**Workflow agents**")
    st.markdown("1. Planner")
    st.markdown("2. Reconciliation")
    st.markdown("3. Investigation")
    st.markdown("4. Action")
    st.markdown("5. Critic / Validation")
    st.divider()
    st.caption("No paid API or external model required. Agents use transparent Python tools and rules.")

st.subheader("1 · Data input")
if source == "Built-in demo data":
    st.write("The demo includes legitimate deductions, an incorrect settlement, a missing bank deposit, a duplicate deposit, and an incomplete-evidence case.")
    if st.button("Load synthetic demo data", type="primary", use_container_width=True):
        st.session_state.input_data = create_demo_data()
        st.session_state.results = None
else:
    st.write("Upload the four CSV files. Required columns are shown below. Order and settlement identifiers should use the same order ID.")
    with st.expander("Required CSV schema"):
        st.code(
            "orders.csv: order_id, order_amount, commission, shipping_fee, other_fee, refund_amount, expected_settlement\\n"
            "settlements.csv: order_id, settlement_amount, settlement_date\\n"
            "refunds.csv: order_id, refund_amount, refund_status\\n"
            "bank.csv: order_id, deposit_amount, deposit_date, bank_reference",
            language="text",
        )
    up_orders = st.file_uploader("Orders CSV", type=["csv"], key="orders")
    up_settlements = st.file_uploader("Settlement report CSV", type=["csv"], key="settlements")
    up_refunds = st.file_uploader("Refunds CSV", type=["csv"], key="refunds")
    up_bank = st.file_uploader("Bank transactions CSV", type=["csv"], key="bank")
    if st.button("Load uploaded files", type="primary"):
        if not all([up_orders, up_settlements, up_refunds, up_bank]):
            st.error("Please upload all four CSV files.")
        else:
            try:
                data = {
                    "orders": pd.read_csv(up_orders),
                    "settlements": pd.read_csv(up_settlements),
                    "refunds": pd.read_csv(up_refunds),
                    "bank": pd.read_csv(up_bank),
                }
                errors = validate_upload(data)
                if errors:
                    st.error("Upload validation failed:\n- " + "\n- ".join(errors))
                    st.session_state.input_data = None
                else:
                    st.session_state.input_data = data
                    st.session_state.results = None
                    st.success("Files loaded and schema validated.")
            except Exception as exc:
                st.error(f"Could not read CSV files: {exc}")

if st.session_state.input_data is not None:
    data = st.session_state.input_data
    with st.expander("Preview input records", expanded=False):
        tabs = st.tabs(["Orders", "Settlements", "Refunds", "Bank"])
        for tab, key in zip(tabs, ["orders", "settlements", "refunds", "bank"]):
            with tab:
                st.dataframe(data[key], use_container_width=True, hide_index=True)

    st.subheader("2 · Run agentic investigation")
    st.write("The orchestrator executes each specialist agent, passes findings between them, and only publishes cases that pass deterministic validation.")
    if st.button("▶ Run RevenueLeak AI workflow", type="primary", use_container_width=True):
        with st.spinner("Agents are planning, reconciling, investigating, prioritising and validating…"):
            st.session_state.results = run_agentic_workflow(data)

if st.session_state.results is not None:
    result = st.session_state.results
    cases = result["cases"]
    summary = result["summary"]
    st.divider()
    st.subheader("3 · Investigation dashboard")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders analysed", summary["orders_analysed"])
    c2.metric("Cases detected", summary["cases_detected"])
    c3.metric("Validated cases", summary["validated_cases"])
    c4.metric("Net unexplained difference", f"₹{summary['net_unexplained_difference']:,.2f}")

    if not cases.empty:
        high = int((cases["priority"] == "High").sum())
        medium = int((cases["priority"] == "Medium").sum())
        low = int((cases["priority"] == "Low").sum())
        st.caption(f"Priority distribution · High: {high} · Medium: {medium} · Low: {low}")
        display_cols = ["case_id", "order_id", "issue_type", "expected_settlement", "settlement_amount",
                        "deposit_amount", "unexplained_difference", "priority", "validation_status", "case_status"]
        st.dataframe(cases[display_cols], use_container_width=True, hide_index=True)
        selected = st.selectbox("Inspect a case", cases["case_id"].tolist())
        case = cases.loc[cases["case_id"] == selected].iloc[0].to_dict()
        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Evidence & explanation")
            st.write(case["explanation"])
            st.write("**Evidence checks**")
            for item in case["evidence"]:
                st.write(f"• {item}")
            st.write(f"**Expected settlement:** ₹{case['expected_settlement']:,.2f}")
            st.write(f"**Recorded settlement:** ₹{case['settlement_amount']:,.2f}")
            st.write(f"**Bank deposit:** ₹{case['deposit_amount']:,.2f}")
            st.write(f"**Unexplained difference:** ₹{case['unexplained_difference']:,.2f}")
        with right:
            st.markdown("#### Recommended next action")
            st.info(case["recommendation"])
            st.write(f"**Priority:** {case['priority']}")
            st.write(f"**Validation:** {case['validation_status']}")
            st.write(f"**Case status:** {case['case_status']}")
            st.caption("Recommendations are drafts. No provider is contacted and no financial action is executed automatically.")

    st.subheader("4 · Agent trace / audit trail")
    for event in result["trace"]:
        with st.expander(f"{event['step']} · {event['agent']} · {event['status']}"):
            st.write(event["message"])
            if event.get("details"):
                st.json(event["details"])

    st.subheader("5 · Validation report")
    st.write(f"**Overall status:** {result['validation']['overall_status']}")
    for check in result["validation"]["checks"]:
        st.write(("✅ " if check["passed"] else "⚠️ ") + check["name"] + " — " + check["details"])

    csv_bytes = build_case_report_csv(cases)
    st.download_button("⬇ Download case report (CSV)", data=csv_bytes,
                       file_name="revenueleak_case_report.csv", mime="text/csv")
    st.download_button("⬇ Download agent trace (JSON)", data=json.dumps(result["trace"], indent=2),
                       file_name="revenueleak_agent_trace.json", mime="application/json")

st.divider()
st.markdown('<p class="small-note">PoC notice: this is a teaching prototype using synthetic records or user-supplied CSVs. It is not accounting advice, does not connect to a marketplace or bank, and treats discrepancies as investigation leads—not proof of loss.</p>', unsafe_allow_html=True)
