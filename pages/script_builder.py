import pandas as pd
import streamlit as st

from display_utils import truncate_dataframe_for_display
from gemini_utils import generate_voicebot_script_with_gemini

DEFAULT_CLIENT_SCRIPT = (
    "Hello, this is a reminder about your account. Can you make a payment today? "
    "If not, please tell us when you can pay. If you have questions, we can connect you to support."
)

DEFAULT_GOALS = (
    "Verify the right party, ask for payment, handle common objections, and escalate sensitive cases."
)

DEFAULT_CONSTRAINTS = (
    "Do not use threatening language. Do not discuss account details before verification. "
    "Escalate disputes, already-paid claims, and requests for a human."
)


def _render_call_flow(call_flow):
    for idx, step in enumerate(call_flow, start=1):
        st.write(f"**{idx}.** {step}")


def render_script_builder_page(filtered):
    st.title("Script Builder")
    st.caption("Turn a client call script into a structured voice-agent flow and prompt.")

    if "saved_script_builds" not in st.session_state:
        st.session_state.saved_script_builds = []

    if len(filtered) > 0:
        clients = sorted(filtered["client"].unique())
        voicebots = sorted(filtered["voicebot"].unique())
    else:
        clients = ["Atlas Bank"]
        voicebots = ["Hannah"]

    st.subheader("Script Setup")
    c1, c2 = st.columns(2)
    with c1:
        client = st.selectbox("Client", clients, key="script_client")
    with c2:
        voicebot = st.selectbox("Voicebot", voicebots, key="script_voicebot")

    client_script = st.text_area(
        "Client-provided call script",
        value=DEFAULT_CLIENT_SCRIPT,
        height=170,
        key="client_script_input",
    )
    goals = st.text_area(
        "Call goals",
        value=DEFAULT_GOALS,
        height=90,
        key="script_goals",
    )
    constraints = st.text_area(
        "Guardrails / constraints",
        value=DEFAULT_CONSTRAINTS,
        height=110,
        key="script_constraints",
    )

    if st.button("Generate Voicebot Script", type="primary"):
        with st.spinner("Structuring script and drafting prompt..."):
            result = generate_voicebot_script_with_gemini(
                client=client,
                voicebot=voicebot,
                client_script=client_script,
                goals=goals,
                constraints=constraints,
            )
            st.session_state["last_script_build"] = result
            st.session_state["last_script_build_inputs"] = {
                "client": client,
                "voicebot": voicebot,
            }

    st.subheader("Generated Flow & Prompt")
    result = st.session_state.get("last_script_build")

    if result is None:
        st.info("Generate a script to review the structured flow and prompt.")
    elif isinstance(result, dict) and "error" in result:
        st.error(result["error"])
    else:
        call_flow = result.get("call_flow", [])
        prompt = result.get("voice_agent_prompt", "")
        assumptions = result.get("assumptions", [])

        st.markdown("**Structured call flow**")
        _render_call_flow(call_flow)

        edited_prompt = st.text_area(
            "Review/edit voice-agent prompt",
            value=prompt,
            height=260,
            key="edited_voice_agent_prompt",
        )

        if assumptions:
            with st.expander("Assumptions to confirm with client", expanded=False):
                for assumption in assumptions:
                    st.markdown(f"- {assumption}")

        if st.button("Save Script Build"):
            inputs = st.session_state.get("last_script_build_inputs", {})
            st.session_state.saved_script_builds.append({
                "client": inputs.get("client", client),
                "voicebot": inputs.get("voicebot", voicebot),
                "call_flow": " | ".join(call_flow),
                "voice_agent_prompt": edited_prompt,
            })
            st.success("Script build saved.")

    st.subheader("Saved Script Builds")
    if st.session_state.saved_script_builds:
        saved_df = truncate_dataframe_for_display(
            pd.DataFrame(st.session_state.saved_script_builds),
            columns=["call_flow", "voice_agent_prompt"],
        )
        st.dataframe(saved_df, use_container_width=True)
    else:
        st.info("No saved script builds yet.")
