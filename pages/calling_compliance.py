import pandas as pd
import streamlit as st

from display_utils import truncate_dataframe_for_display

HOLIDAYS_2026 = {
    "2026-01-01": "New Year's Day",
    "2026-01-19": "Martin Luther King Jr. Day",
    "2026-05-25": "Memorial Day",
    "2026-06-19": "Juneteenth",
    "2026-07-04": "Independence Day",
    "2026-09-07": "Labor Day",
    "2026-11-26": "Thanksgiving Day",
    "2026-12-25": "Christmas Day",
}


def _allowed_window_for_day(call_date, weekday_start, weekday_end, saturday_start, saturday_end):
    weekday = call_date.weekday()
    if weekday < 5:
        return weekday_start, weekday_end, "Weekday"
    if weekday == 5:
        return saturday_start, saturday_end, "Saturday"
    return None, None, "Sunday"


def build_calling_compliance_report(
    df,
    weekday_start=9,
    weekday_end=20,
    saturday_start=10,
    saturday_end=16,
    block_sundays=True,
    block_holidays=True,
):
    report = df.copy()
    report["call_date"] = pd.to_datetime(report["date"]).dt.date
    report["call_time"] = pd.to_datetime(report["local_call_time"], format="%H:%M").dt.time
    report["call_hour_decimal"] = (
        pd.to_datetime(report["local_call_time"], format="%H:%M").dt.hour
        + pd.to_datetime(report["local_call_time"], format="%H:%M").dt.minute / 60
    )
    report["holiday_name"] = report["date"].map(HOLIDAYS_2026)

    rows = []
    for _, row in report.iterrows():
        call_date = pd.to_datetime(row["date"])
        allowed_start, allowed_end, day_type = _allowed_window_for_day(
            call_date,
            weekday_start,
            weekday_end,
            saturday_start,
            saturday_end,
        )

        issues = []
        if block_holidays and pd.notna(row["holiday_name"]):
            issues.append(f"Holiday: {row['holiday_name']}")
        if block_sundays and day_type == "Sunday":
            issues.append("Sunday calling blocked")
        elif allowed_start is not None:
            call_hour = row["call_hour_decimal"]
            if call_hour < allowed_start or call_hour >= allowed_end:
                issues.append(f"Outside {day_type.lower()} window ({allowed_start}:00-{allowed_end}:00)")

        rows.append({
            "call_id": row["call_id"],
            "client": row["client"],
            "voicebot": row["voicebot"],
            "date": row["date"],
            "state": row["state"],
            "local_call_time": row["local_call_time"],
            "day_type": day_type,
            "holiday_name": row["holiday_name"] if pd.notna(row["holiday_name"]) else "",
            "calling_window_issue": " | ".join(issues),
            "is_calling_window_issue": len(issues) > 0,
        })

    return pd.DataFrame(rows)


def render_calling_compliance_page(filtered):
    st.title("Calling Compliance")
    st.caption("Filter call attempts for timing risks like Sunday calls, after-hours calls, and holidays.")

    if len(filtered) == 0:
        st.info("No calls match the current filters. Adjust sidebar filters to continue.")
        return

    report = build_calling_compliance_report(filtered)
    sunday_calls = report[report["day_type"] == "Sunday"].copy()
    holiday_calls = report[report["holiday_name"] != ""].copy()
    after_hours = report[
        report["calling_window_issue"].str.contains("Outside", na=False)
    ].copy()
    all_flagged = report[report["is_calling_window_issue"] == True].copy()

    st.subheader("Audit Filter")
    audit_options = {
        "All flagged timing issues": all_flagged,
        "Sunday calls": sunday_calls,
        "After-hours calls": after_hours,
        "Holiday calls": holiday_calls,
    }
    audit_type = st.selectbox("Show calls for", list(audit_options.keys()))
    selected_df = audit_options[audit_type]

    st.subheader("Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Calls Checked", len(report))
    c2.metric("Sunday Calls", len(sunday_calls))
    c3.metric("After-Hours Calls", len(after_hours))
    c4.metric("Holiday Calls", len(holiday_calls))

    st.subheader(audit_type)
    if len(selected_df) == 0:
        st.success("No calls found for this audit filter.")
    else:
        st.dataframe(
            truncate_dataframe_for_display(
                selected_df[
                    [
                        "call_id",
                        "client",
                        "voicebot",
                        "date",
                        "state",
                        "local_call_time",
                        "day_type",
                        "holiday_name",
                        "calling_window_issue",
                    ]
                ],
                columns=["calling_window_issue"],
            ),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Holiday calendar", expanded=False):
        holiday_df = pd.DataFrame(
            [{"date": date, "holiday": name} for date, name in HOLIDAYS_2026.items()]
        )
        st.dataframe(holiday_df, use_container_width=True, hide_index=True)
