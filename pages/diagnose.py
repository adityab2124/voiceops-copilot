import streamlit as st
import pandas as pd

from display_utils import render_severity, truncate_dataframe_for_display
from gemini_utils import (
    generate_compliance_response_with_gemini,
    generate_diagnosis_with_gemini,
    generate_prompt_fix_with_gemini,
    offline_compliance_response,
    offline_diagnosis,
)

MODES = {
    "QA Review": "calls flagged for QA review",
    "Payment Objection": "calls with payment objection language",
    "Compliance": "calls with compliance-risk language",
}

DEFAULT_AGENT_PROMPT = (
    "You are a payment reminder voice agent. Ask the customer if they can make a payment today. "
    "If they say no, ask once more if they can make the full payment today. "
    "If they still decline, end the call politely."
)


def _get_queue(filtered, mode):
    if mode == "QA Review":
        queue = filtered[filtered["needs_qa_review"] == True].copy()
        columns = [
            "call_id", "client", "voicebot", "business_outcome",
            "qa_review_flag", "qa_severity", "compliance_flag", "call_duration_sec",
        ]
    elif mode == "Payment Objection":
        queue = filtered[filtered["is_payment_objection"] == True].copy()
        columns = [
            "call_id", "client", "voicebot", "business_outcome",
            "qa_review_flag", "call_duration_sec",
        ]
    else:
        queue = filtered[filtered["compliance_flag"] == True].copy()
        columns = [
            "call_id", "client", "voicebot", "state",
            "business_outcome", "qa_evidence",
        ]
    return queue, columns


def _normalize_diagnosis(result, row, mode):
    if "error" in result:
        fallback = offline_diagnosis(row, mode)
        return fallback, result["error"]

    return {
        "what_went_wrong": result.get("what_went_wrong", ""),
        "evidence": result.get("evidence") or result.get("evidence_from_transcript", ""),
        "recommended_fix": result.get("recommended_fix", ""),
    }, None


def _render_diagnosis(diagnosis):
    st.subheader("Diagnosis")
    st.write(f"**What went wrong:** {diagnosis['what_went_wrong']}")
    st.write(f"**Evidence:** {diagnosis['evidence']}")
    st.write(f"**Recommended fix:** {diagnosis['recommended_fix']}")


def _render_compliance_response(response, row, diagnosis, client_request):
    if "error" in response:
        st.error(response["error"])
        response = offline_compliance_response(row, diagnosis, client_request)

    bullets = response.get("summary_bullets", [])
    if bullets:
        st.markdown("**Summary**")
        for bullet in bullets:
            st.markdown(f"- {bullet}")

    client_message = response.get("client_message_draft", "")
    edited_message = st.text_area(
        "Client message draft",
        value=client_message,
        height=220,
        key=f"client_message_{row['call_id']}",
    )

    if st.button("Save Compliance Response", key="save_compliance"):
        st.session_state.saved_compliance_responses.append({
            "call_id": row["call_id"],
            "client": row["client"],
            "voicebot": row["voicebot"],
            "summary": " | ".join(bullets),
            "client_message_draft": edited_message,
        })
        st.success("Compliance response saved.")


def _render_prompt_fix(row, mode, selected_call_id, last_diagnosis):
    st.subheader("Fix & Generate New Prompt")
    current_prompt = st.text_area(
        "Current agent prompt",
        value=DEFAULT_AGENT_PROMPT,
        height=120,
        key=f"current_prompt_{mode}_{selected_call_id}",
    )

    if st.button("Generate New Prompt", key=f"generate_prompt_{mode}"):
        with st.spinner("Generating updated prompt..."):
            prompt_result = generate_prompt_fix_with_gemini(
                row["transcript"],
                current_prompt,
                diagnosis=last_diagnosis,
            )
            st.session_state[f"last_prompt_{mode}"] = prompt_result
            st.session_state[f"last_prompt_call_{mode}"] = selected_call_id

    last_prompt = st.session_state.get(f"last_prompt_{mode}")
    last_prompt_call = st.session_state.get(f"last_prompt_call_{mode}")

    if last_prompt_call == selected_call_id and last_prompt is not None:
        if isinstance(last_prompt, dict) and "error" in last_prompt:
            st.error(last_prompt["error"])
        else:
            updated_prompt = last_prompt.get("updated_prompt", "")
            edited_prompt = st.text_area(
                "Review/edit updated prompt",
                value=updated_prompt,
                height=180,
                key=f"edited_prompt_{mode}_{selected_call_id}",
            )

            if st.button("Save Prompt Update", key=f"save_{mode}"):
                st.session_state.saved_prompt_updates.append({
                    "call_id": row["call_id"],
                    "client": row["client"],
                    "voicebot": row["voicebot"],
                    "mode": mode,
                    "business_outcome": row["business_outcome"],
                    "what_went_wrong": last_diagnosis["what_went_wrong"],
                    "updated_prompt": edited_prompt,
                })
                st.success("Prompt update saved.")


def render_diagnose_page(filtered):
    st.title("Diagnose & Troubleshoot")
    st.caption("Pick a flagged call, review the transcript, run a diagnosis, and take the next action.")

    if len(filtered) == 0:
        st.info("No calls match the current filters. Adjust sidebar filters to continue.")
        return

    if "saved_prompt_updates" not in st.session_state:
        st.session_state.saved_prompt_updates = []
    if "saved_compliance_responses" not in st.session_state:
        st.session_state.saved_compliance_responses = []

    st.subheader("Diagnostic Mode")
    mode = st.selectbox("Diagnostic mode", list(MODES.keys()), key="diagnose_mode")
    queue, queue_columns = _get_queue(filtered, mode)

    if len(queue) == 0:
        st.info("No calls match this mode for the current filters.")
        return

    st.subheader("Call Queue")
    st.caption(f"{len(queue)} {MODES[mode]}.")
    queue_display = queue[queue_columns].copy()
    truncate_cols = [col for col in ["qa_evidence", "transcript"] if col in queue_display.columns]
    st.dataframe(
        truncate_dataframe_for_display(queue_display, columns=truncate_cols),
        use_container_width=True,
    )

    selected_call_id = st.selectbox(
        "Select a call to review",
        queue["call_id"].tolist(),
        key=f"select_{mode}",
    )
    row = queue[queue["call_id"] == selected_call_id].iloc[0]

    st.subheader("Call Details")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Client", row["client"])
    c2.metric("Voicebot", row["voicebot"])
    c3.metric("Outcome", row["business_outcome"])
    c4.metric("Flag", row.get("qa_review_flag", "—"))

    severity = row.get("qa_severity")
    if pd.notna(severity) and str(severity).strip():
        render_severity(severity)

    st.subheader("Transcript")
    with st.container(border=True):
        st.write(row["transcript"])

    st.subheader("Analysis")

    if st.button("Run Diagnosis", type="primary", key=f"run_{mode}"):
        with st.spinner("Analyzing transcript..."):
            similar_count = int(filtered["compliance_flag"].sum()) if mode == "Compliance" else 0
            result = generate_diagnosis_with_gemini(row, mode, similar_count)
            diagnosis, error = _normalize_diagnosis(result, row, mode)
            st.session_state[f"last_diagnosis_{mode}"] = diagnosis
            st.session_state[f"last_diagnosis_error_{mode}"] = error
            st.session_state[f"last_call_{mode}"] = selected_call_id
            st.session_state.pop(f"last_prompt_{mode}", None)
            st.session_state.pop(f"last_compliance_{mode}", None)

    last_call = st.session_state.get(f"last_call_{mode}")
    last_diagnosis = st.session_state.get(f"last_diagnosis_{mode}")

    if last_call == selected_call_id and last_diagnosis is not None:
        diagnosis_error = st.session_state.get(f"last_diagnosis_error_{mode}")
        if diagnosis_error:
            st.warning(f"Gemini unavailable — showing rule-based diagnosis. ({diagnosis_error})")

        _render_diagnosis(last_diagnosis)

        if mode == "Compliance":
            st.subheader("Draft Client Response")
            client_request = st.text_area(
                "Client request or escalation note (optional)",
                placeholder="e.g. Client emailed asking for a written summary and customer-facing reply.",
                height=80,
                key=f"client_request_{selected_call_id}",
            )

            if st.button("Draft Response", key="draft_compliance_response"):
                with st.spinner("Drafting compliance summary and client message..."):
                    similar_count = int(filtered["compliance_flag"].sum())
                    response = generate_compliance_response_with_gemini(
                        row,
                        last_diagnosis,
                        similar_count,
                        client_request,
                    )
                    st.session_state[f"last_compliance_{mode}"] = response
                    st.session_state[f"last_compliance_call_{mode}"] = selected_call_id
                    st.session_state[f"last_compliance_request_{mode}"] = client_request

            last_compliance = st.session_state.get(f"last_compliance_{mode}")
            last_compliance_call = st.session_state.get(f"last_compliance_call_{mode}")
            saved_request = st.session_state.get(f"last_compliance_request_{mode}", client_request)

            if last_compliance_call == selected_call_id and last_compliance is not None:
                _render_compliance_response(last_compliance, row, last_diagnosis, saved_request)
        else:
            _render_prompt_fix(row, mode, selected_call_id, last_diagnosis)

    if mode == "Compliance":
        st.subheader("Saved Compliance Responses")
        if st.session_state.saved_compliance_responses:
            saved_df = truncate_dataframe_for_display(
                pd.DataFrame(st.session_state.saved_compliance_responses),
                columns=["summary", "client_message_draft"],
            )
            st.dataframe(saved_df, use_container_width=True)
        else:
            st.info("No saved compliance responses yet.")
    else:
        st.subheader("Saved Prompt Updates")
        if st.session_state.saved_prompt_updates:
            saved_df = truncate_dataframe_for_display(
                pd.DataFrame(st.session_state.saved_prompt_updates),
                columns=["what_went_wrong", "updated_prompt"],
            )
            st.dataframe(saved_df, use_container_width=True)
        else:
            st.info("No saved prompt updates yet.")
