import pandas as pd
import streamlit as st


def truncate_text(value, max_len=80):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def truncate_dataframe_for_display(df, columns=None, max_len=80):
    display_df = df.copy()
    target_cols = columns or [
        col for col in display_df.columns if display_df[col].dtype == object
    ]
    for col in target_cols:
        if col in display_df.columns:
            display_df[col] = display_df[col].apply(lambda v: truncate_text(v, max_len))
    return display_df


def render_severity(severity):
    level = str(severity).lower().strip()
    label = f"**Severity:** {severity}"
    if level == "high":
        st.error(label)
    elif level == "medium":
        st.warning(label)
    elif level == "low":
        st.info(label)
    else:
        st.write(label)


def render_priority(priority):
    level = str(priority).lower().strip()
    label = f"**Priority:** {priority}"
    if level == "high":
        st.error(label)
    elif level == "medium":
        st.warning(label)
    elif level == "low":
        st.info(label)
    else:
        st.write(label)


def format_rate(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "0.0%"
    return f"{float(value):.1f}%"


def format_analytics_summary_table(df):
    display = df.copy()
    rate_cols = [
        col for col in display.columns
        if col.endswith("_rate") or col == "share_of_calls"
    ]
    int_cols = [
        "total_calls",
        "answered_calls",
        "right_party_contacts",
        "payments",
        "operational_failures",
        "qa_reviews",
        "compliance_flags",
    ]
    for col in int_cols:
        if col in display.columns:
            display[col] = display[col].fillna(0).astype(int)
    for col in rate_cols:
        if col in display.columns:
            display[col] = display[col].apply(format_rate)
    return display
