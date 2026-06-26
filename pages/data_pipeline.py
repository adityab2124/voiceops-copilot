import streamlit as st
import pandas as pd

from display_utils import truncate_dataframe_for_display

SCHEMA_DICTIONARY = [
    ("call_id", True, "Unique call identifier", "Raw"),
    ("client", True, "Enterprise customer account", "Raw"),
    ("voicebot", True, "Voice agent handling the call", "Raw"),
    ("date", True, "Call date", "Raw"),
    ("month", False, "Call month used for trend filtering", "Derived"),
    ("state", True, "Customer region for compliance / calling-hour checks", "Raw"),
    ("local_call_time", True, "Call time in customer local timezone", "Raw"),
    ("answered", True, "Whether someone answered the call", "Raw"),
    ("right_party_contact", True, "Whether the bot reached the intended account holder", "Raw"),
    ("outcome / business_outcome", True, "Customer interaction result", "Raw → Derived"),
    ("payment_collected", True, "Whether the call led to payment", "Raw"),
    ("failed / operational_failure", True, "Call execution failure like no-answer or dropped call", "Raw → Derived"),
    ("operational_failure_reason", False, "Specific operational failure type", "Derived"),
    ("call_duration_sec", True, "Call length in seconds", "Raw"),
    ("qa_flag / client_provided_flag", True, "Upstream/client-provided QA label (comparison only)", "Provided label"),
    ("needs_qa_review", False, "Whether our detection layer flagged the call", "Derived"),
    ("qa_review_flag", False, "Detected QA category from transcript heuristics", "Derived"),
    ("qa_severity", False, "Detected severity from transcript heuristics", "Derived"),
    ("qa_evidence", False, "Evidence snippet supporting the detected flag", "Derived"),
    ("compliance_flag", False, "Derived compliance risk from transcript", "Derived"),
    ("is_payment_objection", False, "Whether transcript matches payment objection terms", "Derived"),
    ("transcript", True, "Call transcript used for QA triage and prompt updates", "Raw"),
]


def _get_raw_df():
    if st.session_state.get("active_call_log_df") is not None:
        return st.session_state.active_call_log_df.copy()
    return pd.read_csv("sample_calls.csv")


def render_data_pipeline_page(df, filtered):
    st.title("Data Pipeline")
    st.caption("Raw call-log layer that feeds downstream TAM workflows.")
    st.caption(
        "This raw log is the single source for every page — regenerate it and all analytics, "
        "QA flags, and diagnoses recompute live."
    )

    if st.button("🔄 Generate New Raw Dataset", type="primary"):
        from generate_sample_data import generate_raw_call_log

        st.session_state.active_call_log_df = generate_raw_call_log(seed=None)
        st.cache_data.clear()
        st.rerun()

    raw_df = _get_raw_df()

    if len(raw_df) == 0:
        st.info("No raw call data available. Generate a new dataset to get started.")
        return

    st.subheader("Raw Call Log")
    st.dataframe(
        truncate_dataframe_for_display(raw_df, columns=["transcript"]),
        use_container_width=True,
    )

    with st.expander("Schema & Column Dictionary", expanded=False):
        dictionary = pd.DataFrame(
            SCHEMA_DICTIONARY,
            columns=["Column", "Required in upload", "Meaning", "Source"],
        )
        st.dataframe(dictionary, use_container_width=True)
