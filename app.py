import streamlit as st

from data_utils import apply_filters, load_data
from pages.account_health import render_account_health_page
from pages.calling_compliance import render_calling_compliance_page
from pages.data_pipeline import render_data_pipeline_page
from pages.diagnose import render_diagnose_page
from pages.engineering_ticket import render_engineering_ticket_page
from pages.script_builder import render_script_builder_page

st.set_page_config(page_title="VoiceOps Copilot", layout="wide")

df = load_data()

st.sidebar.title("VoiceOps Copilot")

page = st.sidebar.radio(
    "Navigation",
    [
        "Data Pipeline",
        "Script Builder",
        "Analytics",
        "Diagnose & Troubleshoot",
        "Engineering Ticket Generator",
        "Calling Compliance",
    ],
)

filtered = apply_filters(df)

if page == "Data Pipeline":
    render_data_pipeline_page(df, filtered)
elif page == "Script Builder":
    render_script_builder_page(filtered)
elif page == "Analytics":
    render_account_health_page(filtered)
elif page == "Diagnose & Troubleshoot":
    render_diagnose_page(filtered)
elif page == "Engineering Ticket Generator":
    render_engineering_ticket_page(filtered)
elif page == "Calling Compliance":
    render_calling_compliance_page(filtered)
