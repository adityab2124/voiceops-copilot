import streamlit as st
import pandas as pd
import plotly.express as px

from display_utils import format_analytics_summary_table, truncate_dataframe_for_display


def _build_bot_health(filtered):
    bot_health = (
        filtered.groupby("voicebot")
        .agg(
            total_calls=("call_id", "count"),
            answered_calls=("answered", "sum"),
            payments=("payment_collected", "sum"),
            operational_failures=("operational_failure", "sum"),
            qa_reviews=("needs_qa_review", "sum"),
        )
        .reset_index()
    )
    bot_health["payment_rate"] = (bot_health["payments"] / bot_health["answered_calls"] * 100).fillna(0)
    bot_health["qa_review_rate"] = (bot_health["qa_reviews"] / bot_health["total_calls"] * 100).fillna(0)
    bot_health["operational_failure_rate"] = (
        bot_health["operational_failures"] / bot_health["total_calls"] * 100
    ).fillna(0)
    return bot_health


def _render_collections_funnel(answer_rate, rpc_rate, ptp_rate, payment_rate):
    funnel_df = pd.DataFrame({
        "stage": ["Answer", "RPC", "Promise-to-Pay", "Payment"],
        "rate": [answer_rate, rpc_rate, ptp_rate, payment_rate],
    })
    funnel_df["rate_label"] = funnel_df["rate"].round(1)

    fig = px.bar(
        funnel_df,
        x="rate",
        y="stage",
        orientation="h",
        text="rate_label",
        title="Collections Funnel",
        category_orders={"stage": ["Answer", "RPC", "Promise-to-Pay", "Payment"]},
    )
    fig.update_layout(showlegend=False, xaxis_title="Rate (%)", yaxis_title="")
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Industry benchmark: PTP from ~80% of contacted debtors.")


def _render_payment_rate_by_voicebot(filtered):
    chart_df = (
        filtered.groupby("voicebot")
        .agg(answered_calls=("answered", "sum"), payments=("payment_collected", "sum"))
        .reset_index()
    )
    chart_df["payment_rate"] = (chart_df["payments"] / chart_df["answered_calls"] * 100).fillna(0).round(1)
    fig = px.bar(
        chart_df.sort_values("payment_rate"),
        x="voicebot",
        y="payment_rate",
        color="voicebot",
        text="payment_rate",
        title="Payment Rate by Voicebot",
    )
    fig.update_layout(showlegend=False)
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


def render_account_health_page(filtered):
    st.title("Analytics")
    st.caption("Collections funnel performance across clients and voicebots.")

    if len(filtered) == 0:
        st.info("No calls match the current filters. Adjust sidebar filters to view analytics.")
        return

    total_calls = len(filtered)
    answered_calls = filtered["answered"].sum()
    right_party_contacts = filtered["right_party_contact"].sum()
    payments = filtered["payment_collected"].sum()
    compliance_flags = int(filtered["compliance_flag"].sum())
    ptp_count = (filtered["business_outcome"] == "promise_to_pay").sum()

    answer_rate = answered_calls / total_calls * 100 if total_calls else 0
    rpc_rate = right_party_contacts / answered_calls * 100 if answered_calls else 0
    ptp_rate = ptp_count / right_party_contacts * 100 if right_party_contacts else 0
    payment_rate = payments / answered_calls * 100 if answered_calls else 0

    st.subheader("TAM Insights")
    bot_health = _build_bot_health(filtered)

    if len(bot_health) > 0:
        lowest_payment = bot_health.sort_values("payment_rate").iloc[0]
        highest_qa = bot_health.sort_values("qa_review_rate", ascending=False).iloc[0]
        highest_failure = bot_health.sort_values("operational_failure_rate", ascending=False).iloc[0]

        i1, i2, i3 = st.columns(3)
        i1.info(
            f"Lowest payment rate: **{lowest_payment['voicebot']}** "
            f"at **{lowest_payment['payment_rate']:.1f}%**"
        )
        i2.warning(
            f"Highest QA review rate: **{highest_qa['voicebot']}** "
            f"at **{highest_qa['qa_review_rate']:.1f}%**"
        )
        i3.error(
            f"Highest operational failure rate: **{highest_failure['voicebot']}** "
            f"at **{highest_failure['operational_failure_rate']:.1f}%**"
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Calls", total_calls)
    c2.metric("Answer Rate", f"{answer_rate:.1f}%")
    c3.metric("RPC Rate", f"{rpc_rate:.1f}%")
    c4.metric("Payment Rate", f"{payment_rate:.1f}%")

    st.subheader("Collections Funnel")
    _render_collections_funnel(answer_rate, rpc_rate, ptp_rate, payment_rate)

    st.subheader("Payment Rate by Voicebot")
    _render_payment_rate_by_voicebot(filtered)

    st.subheader("Compliance")
    c1, c2 = st.columns([1, 2])
    c1.metric("Compliance Flags", compliance_flags)
    compliance_by_client = (
        filtered.groupby("client")
        .agg(compliance_flags=("compliance_flag", "sum"))
        .reset_index()
        .sort_values("compliance_flags", ascending=False)
    )
    c2.dataframe(
        truncate_dataframe_for_display(compliance_by_client.astype({"compliance_flags": int})),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Voicebot Summary")
    bot_summary = (
        filtered.groupby("voicebot")
        .agg(
            total_calls=("call_id", "count"),
            answered_calls=("answered", "sum"),
            right_party_contacts=("right_party_contact", "sum"),
            payments=("payment_collected", "sum"),
            operational_failures=("operational_failure", "sum"),
            qa_reviews=("needs_qa_review", "sum"),
            compliance_flags=("compliance_flag", "sum"),
        )
        .reset_index()
    )

    bot_summary["share_of_calls"] = (bot_summary["total_calls"] / total_calls * 100).round(1)
    bot_summary["answer_rate"] = (bot_summary["answered_calls"] / bot_summary["total_calls"] * 100).round(1)
    bot_summary["rpc_rate"] = (bot_summary["right_party_contacts"] / bot_summary["answered_calls"] * 100).round(1)
    bot_summary["payment_rate"] = (bot_summary["payments"] / bot_summary["answered_calls"] * 100).round(1)
    bot_summary["operational_failure_rate"] = (bot_summary["operational_failures"] / bot_summary["total_calls"] * 100).round(1)
    bot_summary["qa_review_rate"] = (bot_summary["qa_reviews"] / bot_summary["total_calls"] * 100).round(1)

    st.dataframe(format_analytics_summary_table(bot_summary), use_container_width=True)


# --- Unused secondary charts / tables (kept for quick re-enable) ---
#
# def _render_secondary_charts(filtered):
#     chart_choice = st.selectbox(
#         "Choose chart",
#         [
#             "Answer Rate by Client",
#             "Right-Party Contact Rate by Client",
#             "QA Review Rate by Voicebot",
#             "Operational Failure Rate by Voicebot",
#             "Call Volume by Hour",
#             "Business Outcomes by Voicebot",
#         ],
#     )
#     if chart_choice == "Answer Rate by Client":
#         chart_df = (
#             filtered.groupby("client")
#             .agg(total_calls=("call_id", "count"), answered_calls=("answered", "sum"))
#             .reset_index()
#         )
#         chart_df["answer_rate"] = (chart_df["answered_calls"] / chart_df["total_calls"] * 100).round(1)
#         fig = px.bar(chart_df.sort_values("answer_rate"), x="client", y="answer_rate", color="client", text="answer_rate", title="Answer Rate by Client")
#         fig.update_layout(showlegend=False)
#         fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
#         st.plotly_chart(fig, use_container_width=True)
#     elif chart_choice == "Right-Party Contact Rate by Client":
#         chart_df = (
#             filtered.groupby("client")
#             .agg(answered_calls=("answered", "sum"), right_party_contacts=("right_party_contact", "sum"))
#             .reset_index()
#         )
#         chart_df["rpc_rate"] = (chart_df["right_party_contacts"] / chart_df["answered_calls"] * 100).fillna(0).round(1)
#         fig = px.bar(chart_df.sort_values("rpc_rate"), x="client", y="rpc_rate", color="client", text="rpc_rate", title="Right-Party Contact Rate by Client")
#         fig.update_layout(showlegend=False)
#         fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
#         st.plotly_chart(fig, use_container_width=True)
#     elif chart_choice == "QA Review Rate by Voicebot":
#         chart_df = (
#             filtered.groupby("voicebot")
#             .agg(total_calls=("call_id", "count"), qa_reviews=("needs_qa_review", "sum"))
#             .reset_index()
#         )
#         chart_df["qa_review_rate"] = (chart_df["qa_reviews"] / chart_df["total_calls"] * 100).round(1)
#         fig = px.bar(chart_df.sort_values("qa_review_rate"), x="voicebot", y="qa_review_rate", color="voicebot", text="qa_review_rate", title="QA Review Rate by Voicebot")
#         fig.update_layout(showlegend=False)
#         fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
#         st.plotly_chart(fig, use_container_width=True)
#     elif chart_choice == "Operational Failure Rate by Voicebot":
#         chart_df = (
#             filtered.groupby("voicebot")
#             .agg(total_calls=("call_id", "count"), operational_failures=("operational_failure", "sum"))
#             .reset_index()
#         )
#         chart_df["operational_failure_rate"] = (chart_df["operational_failures"] / chart_df["total_calls"] * 100).round(1)
#         fig = px.bar(chart_df.sort_values("operational_failure_rate"), x="voicebot", y="operational_failure_rate", color="voicebot", text="operational_failure_rate", title="Operational Failure Rate by Voicebot")
#         fig.update_layout(showlegend=False)
#         fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
#         st.plotly_chart(fig, use_container_width=True)
#     elif chart_choice == "Call Volume by Hour":
#         chart_df = filtered.groupby("call_hour").size().reset_index(name="calls")
#         fig = px.line(chart_df, x="call_hour", y="calls", markers=True, title="Call Volume by Local Hour")
#         st.plotly_chart(fig, use_container_width=True)
#     elif chart_choice == "Business Outcomes by Voicebot":
#         chart_df = filtered.groupby(["business_outcome", "voicebot"]).size().reset_index(name="calls")
#         fig = px.bar(chart_df, x="business_outcome", y="calls", color="voicebot", title="Business Outcomes by Voicebot", barmode="stack")
#         st.plotly_chart(fig, use_container_width=True)
#
# def _render_breakdown_tables(filtered):
#     left, right = st.columns(2)
#     with left:
#         st.subheader("Operational Failure Breakdown")
#         failure_breakdown = (
#             filtered[filtered["operational_failure"] == True]
#             .groupby("operational_failure_reason")
#             .size()
#             .reset_index(name="calls")
#         )
#         st.dataframe(failure_breakdown, use_container_width=True)
#     with right:
#         st.subheader("QA Review Breakdown")
#         qa_breakdown = (
#             filtered[filtered["needs_qa_review"] == True]
#             .groupby("qa_review_flag")
#             .size()
#             .reset_index(name="calls")
#         )
#         st.dataframe(qa_breakdown, use_container_width=True)
#
# def _render_client_summary(filtered, total_calls):
#     st.subheader("Client Summary")
#     client_summary = (
#         filtered.groupby("client")
#         .agg(
#             total_calls=("call_id", "count"),
#             answered_calls=("answered", "sum"),
#             right_party_contacts=("right_party_contact", "sum"),
#             payments=("payment_collected", "sum"),
#             operational_failures=("operational_failure", "sum"),
#             qa_reviews=("needs_qa_review", "sum"),
#             compliance_flags=("compliance_flag", "sum"),
#         )
#         .reset_index()
#     )
#     client_summary["answer_rate"] = (client_summary["answered_calls"] / client_summary["total_calls"] * 100).round(1)
#     client_summary["rpc_rate"] = (client_summary["right_party_contacts"] / client_summary["answered_calls"] * 100).round(1)
#     client_summary["payment_rate"] = (client_summary["payments"] / client_summary["answered_calls"] * 100).round(1)
#     client_summary["operational_failure_rate"] = (client_summary["operational_failures"] / client_summary["total_calls"] * 100).round(1)
#     client_summary["qa_review_rate"] = (client_summary["qa_reviews"] / client_summary["total_calls"] * 100).round(1)
#     st.dataframe(client_summary, use_container_width=True)
