import streamlit as st
import pandas as pd

from display_utils import render_priority, truncate_dataframe_for_display
from gemini_utils import (
    generate_engineering_ticket_with_gemini,
    generate_sample_client_request_with_gemini,
)

REQUEST_SOURCES = ["Email", "Slack", "Account Review", "QA Finding", "Implementation Call", "Other"]
PRIORITIES = ["Low", "Medium", "High"]

DEFAULT_CLIENT_REQUEST = (
    "Client wants the bot to support credit-card payment links when a borrower agrees to pay today."
)
DEFAULT_CURRENT_BEHAVIOR = "The bot can discuss payment but does not send a secure payment link."
DEFAULT_DESIRED_BEHAVIOR = (
    "When the borrower agrees to pay today and is eligible, the bot should send "
    "a secure credit-card payment link by SMS."
)


def render_engineering_ticket_page(filtered):
    st.title("Engineering Ticket Generator")
    st.caption("Translate a client request into a clear engineering ticket for developers.")

    if len(filtered) == 0:
        st.info("No calls match the current filters. Adjust sidebar filters to continue.")
        return

    if "saved_engineering_tickets" not in st.session_state:
        st.session_state.saved_engineering_tickets = []

    clients = sorted(filtered["client"].unique())
    voicebots = sorted(filtered["voicebot"].unique())
    call_ids = filtered["call_id"].tolist()

    st.subheader("Request Setup")
    c1, c2 = st.columns(2)
    with c1:
        client = st.selectbox("Client", clients)
    with c2:
        voicebot = st.selectbox("Voicebot", voicebots)

    groundable_calls = filtered[
        (filtered["needs_qa_review"] == True) | (filtered["is_payment_objection"] == True)
    ].copy()
    groundable_options = ["None — generate generic request"] + groundable_calls["call_id"].tolist()
    ground_call_id = st.selectbox("Ground request in a real call (optional)", groundable_options)

    if st.button("🎲 Generate Sample Client Request"):
        call_context = None
        if ground_call_id != "None — generate generic request":
            call_context = groundable_calls[
                groundable_calls["call_id"] == ground_call_id
            ].iloc[0].to_dict()

        with st.spinner("Generating sample client request..."):
            sample = generate_sample_client_request_with_gemini(
                client=client,
                voicebot=voicebot,
                call_context=call_context,
            )
            st.session_state["ticket_request_source"] = sample.get("request_source", "Email")
            st.session_state["ticket_client_request"] = sample.get("client_request", "")
            st.session_state["ticket_current_behavior"] = sample.get("current_behavior", "")
            st.session_state["ticket_desired_behavior"] = sample.get("desired_behavior", "")
            st.session_state["ticket_priority"] = sample.get("priority", "Medium")
            if ground_call_id != "None — generate generic request":
                st.session_state["ticket_related_call_ids"] = [ground_call_id]
            st.rerun()

    st.subheader("Client Request")
    request_source = st.selectbox(
        "Request source",
        REQUEST_SOURCES,
        index=REQUEST_SOURCES.index(st.session_state.get("ticket_request_source", "Email"))
        if st.session_state.get("ticket_request_source", "Email") in REQUEST_SOURCES
        else 0,
    )

    priority = st.selectbox(
        "Priority",
        PRIORITIES,
        index=PRIORITIES.index(st.session_state.get("ticket_priority", "Medium"))
        if st.session_state.get("ticket_priority", "Medium") in PRIORITIES
        else 1,
    )
    render_priority(priority)

    related_call_ids = st.multiselect(
        "Related call IDs",
        call_ids,
        default=st.session_state.get("ticket_related_call_ids", []),
    )

    client_request = st.text_area(
        "Client request",
        value=st.session_state.get("ticket_client_request", DEFAULT_CLIENT_REQUEST),
        height=100,
    )

    current_behavior = st.text_area(
        "Current behavior",
        value=st.session_state.get("ticket_current_behavior", DEFAULT_CURRENT_BEHAVIOR),
        height=100,
    )

    desired_behavior = st.text_area(
        "Desired behavior",
        value=st.session_state.get("ticket_desired_behavior", DEFAULT_DESIRED_BEHAVIOR),
        height=100,
    )

    if st.button("Generate Engineering Ticket with Gemini"):
        with st.spinner("Generating engineering ticket..."):
            result = generate_engineering_ticket_with_gemini(
                client=client,
                voicebot=voicebot,
                request_source=request_source,
                client_request=client_request,
                current_behavior=current_behavior,
                desired_behavior=desired_behavior,
                priority=priority,
                related_call_ids=related_call_ids,
            )
            st.session_state["last_engineering_ticket"] = result
            st.session_state["last_engineering_ticket_inputs"] = {
                "client": client,
                "voicebot": voicebot,
                "request_source": request_source,
                "priority": priority,
                "related_call_ids": related_call_ids,
            }

    st.subheader("Generated Ticket")
    if "last_engineering_ticket" in st.session_state:
        result = st.session_state["last_engineering_ticket"]

        if isinstance(result, dict) and "error" in result:
            st.error(result["error"])
        else:
            edited_ticket = st.text_area(
                "Review/edit engineering ticket",
                value=result,
                height=400,
            )

            if st.button("Send to Engineering Queue"):
                inputs = st.session_state.get("last_engineering_ticket_inputs", {})
                st.session_state.saved_engineering_tickets.append({
                    "client": inputs.get("client", client),
                    "voicebot": inputs.get("voicebot", voicebot),
                    "request_source": inputs.get("request_source", request_source),
                    "priority": inputs.get("priority", priority),
                    "related_call_ids": inputs.get("related_call_ids", related_call_ids),
                    "ticket_text": edited_ticket,
                })
                st.success("Ticket saved to simulated engineering queue.")
    else:
        st.info("Generate a ticket to review it here.")

    st.subheader("Saved Engineering Tickets")
    if st.session_state.saved_engineering_tickets:
        saved_df = truncate_dataframe_for_display(
            pd.DataFrame(st.session_state.saved_engineering_tickets),
            columns=["ticket_text"],
        )
        st.dataframe(saved_df, use_container_width=True)
    else:
        st.info("No saved engineering tickets yet.")
