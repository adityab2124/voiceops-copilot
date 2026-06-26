import streamlit as st
import pandas as pd

PAYMENT_OBJECTION_TERMS = [
    "can't pay",
    "cannot pay",
    "lost my job",
    "need more time",
    "payment plan",
]
COMPLIANCE_RISK_TERMS = ["legal action", "you have no choice"]

REQUIRED_UPLOAD_COLUMNS = [
    "call_id",
    "client",
    "voicebot",
    "date",
    "state",
    "local_call_time",
    "answered",
    "right_party_contact",
    "outcome",
    "payment_collected",
    "failed",
    "call_duration_sec",
    "qa_flag",
    "compliance_flag",
    "transcript",
]

DISPLAY_COLUMNS = [
    "call_id",
    "client",
    "voicebot",
    "date",
    "month",
    "state",
    "local_call_time",
    "answered",
    "right_party_contact",
    "business_outcome",
    "payment_collected",
    "operational_failure",
    "operational_failure_reason",
    "needs_qa_review",
    "qa_review_flag",
    "qa_severity",
    "qa_evidence",
    "client_provided_flag",
    "compliance_flag",
    "is_payment_objection",
    "call_duration_sec",
    "transcript",
]


def validate_uploaded_call_log(df):
    missing_columns = [col for col in REQUIRED_UPLOAD_COLUMNS if col not in df.columns]
    return len(missing_columns) == 0, missing_columns


def detect_qa_flag(row):
    transcript = str(row["transcript"]).lower()
    outcome = str(row["business_outcome"])
    duration = float(row["call_duration_sec"])

    for term in COMPLIANCE_RISK_TERMS:
        if term in transcript:
            return (
                "compliance_risk",
                "high",
                f"Transcript contains '{term}'.",
                True,
            )

    if outcome == "call_dropped" and duration < 25:
        return (
            "early_drop",
            "medium",
            f"Call dropped after {duration:.0f} seconds.",
            False,
        )

    if "already paid" in transcript and outcome not in ("already_paid", "payment_collected"):
        return (
            "wrong_outcome",
            "medium",
            "Customer said they already paid but outcome does not reflect that.",
            False,
        )

    for term in PAYMENT_OBJECTION_TERMS:
        if term in transcript:
            return (
                "payment_objection",
                "medium",
                f"Transcript contains payment objection language: '{term}'.",
                False,
            )

    return pd.NA, pd.NA, pd.NA, False


def derive_detection(df):
    df = df.copy()

    detection = df.apply(
        lambda row: pd.Series(
            detect_qa_flag(row),
            index=["qa_review_flag", "qa_severity", "qa_evidence", "compliance_flag"],
        ),
        axis=1,
    )
    df["qa_review_flag"] = detection["qa_review_flag"]
    df["qa_severity"] = detection["qa_severity"]
    df["qa_evidence"] = detection["qa_evidence"]
    df["compliance_flag"] = detection["compliance_flag"]
    df["needs_qa_review"] = df["qa_review_flag"].notna()

    objection_pattern = "|".join(PAYMENT_OBJECTION_TERMS)
    df["is_payment_objection"] = (
        df["transcript"].str.lower().str.contains(objection_pattern, regex=True)
    )

    return df


def normalize_call_log(df):
    df = df.copy()
    df["qa_flag"] = df["qa_flag"].replace(["None", "none", ""], pd.NA)

    df = df.rename(columns={
        "outcome": "business_outcome",
        "failed": "operational_failure",
        "qa_flag": "client_provided_flag",
    })

    def get_operational_failure_reason(row):
        if row["business_outcome"] == "no_answer":
            return "no_answer"
        if row["business_outcome"] == "call_dropped":
            return "call_dropped"
        return "none"

    df["operational_failure_reason"] = df.apply(get_operational_failure_reason, axis=1)
    df["call_hour"] = pd.to_datetime(df["local_call_time"], format="%H:%M").dt.hour
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

    return derive_detection(df)


@st.cache_data
def _load_sample_csv():
    return pd.read_csv("sample_calls.csv")


def load_data():
    if st.session_state.get("active_call_log_df") is not None:
        df = st.session_state.active_call_log_df.copy()
    else:
        df = _load_sample_csv()

    return normalize_call_log(df)


def apply_filters(df):
    st.sidebar.subheader("Filters")

    clients = ["All"] + sorted(df["client"].unique())
    bots = ["All"] + sorted(df["voicebot"].unique())
    months = ["All"] + sorted(df["month"].unique())

    client = st.sidebar.selectbox("Client", clients)
    bot = st.sidebar.selectbox("Voicebot", bots)
    month = st.sidebar.selectbox("Month", months)

    filtered = df.copy()

    if client != "All":
        filtered = filtered[filtered["client"] == client]
    if bot != "All":
        filtered = filtered[filtered["voicebot"] == bot]
    if month != "All":
        filtered = filtered[filtered["month"] == month]

    return filtered
