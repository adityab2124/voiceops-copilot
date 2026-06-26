import json
import random

import google.generativeai as genai
import streamlit as st

OFFLINE_CLIENT_REQUESTS = [
    {
        "request_source": "Email",
        "client_request": (
            "We'd like the voicebot to send a secure credit-card payment link by SMS "
            "when a borrower agrees to pay today."
        ),
        "current_behavior": "The bot can discuss payment but does not send a secure payment link.",
        "desired_behavior": (
            "When the borrower agrees to pay today and is eligible, the bot should send "
            "a secure credit-card payment link by SMS."
        ),
        "priority": "High",
    },
    {
        "request_source": "Slack",
        "client_request": (
            "Our QA team flagged that the bot repeats the full-payment ask when customers "
            "say they can't pay. Can we improve objection handling?"
        ),
        "current_behavior": "The bot asks for full payment again after a hardship objection.",
        "desired_behavior": (
            "The bot should acknowledge hardship and offer eligible alternatives like "
            "partial payment, scheduled payment, or a payment plan."
        ),
        "priority": "Medium",
    },
    {
        "request_source": "Account Review",
        "client_request": (
            "Can we add ACH as a payment option when customers want to pay today but "
            "don't have a card handy?"
        ),
        "current_behavior": "The bot only discusses card payments over the phone.",
        "desired_behavior": "The bot should offer ACH bank transfer when the customer prefers that method.",
        "priority": "Medium",
    },
]


def offline_voicebot_script(client, voicebot, client_script, goals, constraints):
    goals_text = goals.strip() or "Collect payment, handle objections, and escalate when needed."
    constraints_text = constraints.strip() or "Be professional, conservative, and avoid pressure-based language."
    script_excerpt = client_script.strip()[:700] or "No client script provided."

    return {
        "call_flow": [
            "Opening: introduce the voice agent and verify the customer is available to discuss the account.",
            "Identity check: confirm the right party before discussing account details.",
            "Payment ask: ask whether the customer can make a payment today.",
            "Objection handling: acknowledge hardship, offer eligible alternatives, and avoid repeating the same ask.",
            "Escalation: transfer to a human if the customer disputes the balance, says they already paid, asks for a person, or raises compliance-sensitive concerns.",
            "Close: summarize next steps and end politely.",
        ],
        "voice_agent_prompt": (
            f"You are {voicebot}, a payment reminder voice agent for {client}. "
            f"Primary goals: {goals_text} "
            f"Operating constraints: {constraints_text} "
            "Speak clearly and professionally. Verify the right party before discussing account details. "
            "Ask whether the customer can make a payment today. If they cannot pay, acknowledge their situation "
            "and offer only eligible alternatives such as a later payment date, partial payment, payment plan, "
            "or human transfer. Do not use threatening, legal, or pressure-based language. If the customer says "
            "they already paid, disputes the balance, asks for a human, or appears distressed, transfer to a human agent."
        ),
        "assumptions": [
            "Eligibility rules for payment plans or payment methods must be confirmed with the client.",
            "The source script was treated as draft input, not as final compliance-approved language.",
            f"Source script excerpt reviewed: {script_excerpt}",
        ],
    }


def generate_voicebot_script_with_gemini(client, voicebot, client_script, goals, constraints):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return offline_voicebot_script(client, voicebot, client_script, goals, constraints)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are a Technical Account Manager turning a client's call script into a structured voicebot flow.

Create a practical call flow and a ready-to-review voice agent prompt.

Rules:
- Be conservative.
- Do not invent client policy, payment eligibility, vendors, or legal requirements.
- Avoid threatening, legal, or pressure-based language.
- Include escalation when the customer disputes the balance, says they already paid, asks for a human, or expresses distress.
- Keep the call flow concise and ordered.
- Return valid JSON only.

Return JSON schema:
{{
  "call_flow": [
    "Step name: what the agent should do"
  ],
  "voice_agent_prompt": "",
  "assumptions": [
    ""
  ]
}}

Client: {client}
Voicebot: {voicebot}
Goals: {goals}
Constraints: {constraints}

Client script:
{client_script}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
    except Exception:
        return offline_voicebot_script(client, voicebot, client_script, goals, constraints)


def generate_sample_client_request_with_gemini(client, voicebot, call_context=None):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return random.choice(OFFLINE_CLIENT_REQUESTS)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    context_block = ""
    if call_context:
        context_block = f"""
Related call context:
- Outcome: {call_context.get("business_outcome", "")}
- Detected flag: {call_context.get("qa_review_flag", "")}
- Transcript: {call_context.get("transcript", "")}
"""

    prompt = f"""
You are a Technical Account Manager drafting a realistic client request for a collections voicebot.

Write a short client request (email or Slack style) that a client like {client} might send
about their voicebot {voicebot}.

The request should be about a concrete product change — e.g. a new payment option, SMS payment link,
objection-handling fix, escalation improvement, or similar.

Rules:
- Be realistic and specific but do not invent vendor names or compliance policies.
- Keep each field concise (1-3 sentences).
- Return valid JSON only.
{context_block}
Return JSON schema:
{{
  "request_source": "Email | Slack | Account Review | QA Finding | Implementation Call | Other",
  "client_request": "",
  "current_behavior": "",
  "desired_behavior": "",
  "priority": "Low | Medium | High"
}}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
    except Exception:
        return random.choice(OFFLINE_CLIENT_REQUESTS)


def offline_diagnosis(row, mode):
    if mode == "QA Review":
        return {
            "what_went_wrong": f"{row['qa_review_flag']} detected in this call.",
            "evidence": row["qa_evidence"],
            "recommended_fix": "Review transcript and update agent flow or escalate as needed.",
        }
    if mode == "Payment Objection":
        return {
            "what_went_wrong": "The agent did not adequately address the customer's payment objection.",
            "evidence": "Transcript contains payment hardship or objection language.",
            "recommended_fix": (
                "Acknowledge hardship, offer eligible alternatives, and avoid repeating the full-payment ask."
            ),
        }
    return {
        "what_went_wrong": "Transcript may contain pressure-based or regulated-risk language.",
        "evidence": row.get("qa_evidence", ""),
        "recommended_fix": "Contain the pattern, review script compliance, and update agent language.",
    }


def generate_diagnosis_with_gemini(row, mode, similar_count=0):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return offline_diagnosis(row, mode)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    mode_context = {
        "QA Review": (
            "Review this flagged QA call. Focus on whether the flag is valid and what the agent did wrong."
        ),
        "Payment Objection": (
            "Review this payment-objection call. Focus on how the agent handled hardship or refusal to pay."
        ),
        "Compliance": (
            "Review this compliance-risk call. Focus on risky language without making legal conclusions."
        ),
    }[mode]

    fleet_context = ""
    if mode == "Compliance":
        fleet_context = (
            f"\nFleet context: {similar_count} calls in the current filtered dataset "
            "contain similar compliance-risk language."
        )

    prompt = f"""
You are a Technical Account Manager reviewing a flagged financial servicing voicebot call.

{mode_context}

Rules:
- Be conservative.
- Do not invent facts not present in the transcript.
- Do not make legal conclusions.
- Keep each field to one sentence.
- Return valid JSON only.

Return JSON schema:
{{
  "what_went_wrong": "",
  "evidence": "",
  "recommended_fix": ""
}}

Call metadata:
- call_id: {row["call_id"]}
- client: {row["client"]}
- voicebot: {row["voicebot"]}
- business_outcome: {row["business_outcome"]}
- qa_review_flag: {row.get("qa_review_flag", "")}
- compliance_flag: {row.get("compliance_flag", False)}
- call_duration_sec: {row.get("call_duration_sec", "")}
{fleet_context}

Transcript:
{row["transcript"]}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}


def generate_prompt_fix_with_gemini(transcript, current_prompt, diagnosis=None):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return {
            "updated_prompt": (
                f"{current_prompt}\n\n"
                "If the customer expresses hardship or cannot pay today, acknowledge their situation, "
                "offer eligible alternatives, and escalate to a human when requested."
            )
        }

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    diagnosis_block = ""
    if diagnosis:
        diagnosis_block = f"""
Diagnosis:
- What went wrong: {diagnosis.get("what_went_wrong", "")}
- Evidence: {diagnosis.get("evidence", "")}
- Recommended fix: {diagnosis.get("recommended_fix", "")}
"""

    prompt = f"""
You are a Technical Account Manager reviewing a financial servicing voicebot.

Review the current agent prompt and call transcript. Generate a safer, more effective updated prompt.

Rules:
- Be conservative.
- Do not invent client policy.
- Do not use threatening, legal, or pressure-based language.
- If the customer disputes the balance, says they already paid, or asks for a human, recommend escalation.
- Return the full revised prompt text, not just a snippet.
- Return valid JSON only.

Return this JSON schema:
{{
  "updated_prompt": ""
}}

Current agent prompt:
{current_prompt}
{diagnosis_block}
Call transcript:
{transcript}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        result = json.loads(response.text)
        if "updated_prompt" not in result and result.get("updated_prompt_snippet"):
            result["updated_prompt"] = result["updated_prompt_snippet"]
        return result
    except Exception as e:
        return {"error": str(e)}


def generate_qa_analysis_with_gemini(row):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return {"error": "Missing GEMINI_API_KEY. Add it to .streamlit/secrets.toml."}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are a Technical Account Manager reviewing a flagged financial servicing voicebot call.

Review the call metadata and transcript. Generate a QA analysis for the TAM.

Rules:
- Be conservative.
- Do not invent facts not present in the transcript.
- Do not make legal conclusions.
- Flag compliance risk if the transcript contains pressure-based, threatening, or regulated-risk language.
- If the customer says they already paid, disputes balance, asks for a human, or expresses hardship, identify that clearly.
- Keep what_went_wrong, evidence_from_transcript, and recommended_fix to one sentence each.
- Return valid JSON only.

Return JSON schema:
{{
  "issue_category": "",
  "severity": "low | medium | high",
  "qa_decision": "valid_flag | false_positive | needs_manual_review",
  "what_went_wrong": "",
  "evidence_from_transcript": "",
  "recommended_fix": "",
  "client_safe_summary": "",
  "internal_notes": ""
}}

Call metadata:
- call_id: {row["call_id"]}
- client: {row["client"]}
- voicebot: {row["voicebot"]}
- business_outcome: {row["business_outcome"]}
- qa_review_flag: {row["qa_review_flag"]}
- compliance_flag: {row["compliance_flag"]}
- call_duration_sec: {row["call_duration_sec"]}

Transcript:
{row["transcript"]}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}


def offline_compliance_response(row, diagnosis, client_request=""):
    call_time = f"{row.get('date', '')} {row.get('local_call_time', '')}".strip()
    bullets = [
        f"**Client:** {row['client']}",
        f"**Issue:** {diagnosis.get('what_went_wrong', 'Compliance-risk language detected in call transcript.')}",
        f"**Time:** {call_time or 'Not provided'}",
        f"**Call ID:** {row['call_id']}",
        f"**Voicebot:** {row['voicebot']}",
        f"**State:** {row.get('state', '—')}",
        f"**Evidence:** {diagnosis.get('evidence', row.get('qa_evidence', ''))}",
    ]
    if client_request.strip():
        bullets.append(f"**Client request:** {client_request.strip()}")

    client_message = (
        f"Hi {row['client']} team,\n\n"
        f"Thank you for flagging call {row['call_id']} on {call_time or 'the reported date'}. "
        f"We reviewed the transcript and identified language that may create compliance risk. "
        f"We are containing the pattern, reviewing the voicebot script, and will follow up with "
        f"remediation steps shortly.\n\n"
        f"Please let us know if you have additional context or a specific customer complaint we should reference."
    )
    return {
        "summary_bullets": bullets,
        "client_message_draft": client_message,
    }


def generate_compliance_response_with_gemini(row, diagnosis, similar_count=0, client_request=""):
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return offline_compliance_response(row, diagnosis, client_request)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    request_block = ""
    if client_request.strip():
        request_block = f"\nClient request or escalation note:\n{client_request.strip()}"

    prompt = f"""
You are a Technical Account Manager drafting a compliance follow-up for a collections voicebot client.

Use the diagnosis and call metadata to prepare:
1) A short internal summary as bullet points
2) A professional client-facing message ready to send

Rules:
- Be conservative.
- Do NOT make legal conclusions or assert regulatory violations.
- Quote only what the transcript actually says.
- Include client, issue, call time, call ID, voicebot, and state when available.
- Include a "Client request" bullet only if a client request or escalation note was provided.
- Keep the client message professional, factual, and non-defensive.
- Return valid JSON only.

Fleet context: {similar_count} calls in the current filtered dataset contain similar compliance-risk language.

Diagnosis:
- What went wrong: {diagnosis.get("what_went_wrong", "")}
- Evidence: {diagnosis.get("evidence", "")}
- Recommended fix: {diagnosis.get("recommended_fix", "")}
{request_block}

Return JSON schema:
{{
  "summary_bullets": [
    "Client: ...",
    "Issue: ...",
    "Time: ...",
    "Call ID: ...",
    "Voicebot: ...",
    "State: ...",
    "Evidence: ...",
    "Client request: ..."
  ],
  "client_message_draft": ""
}}

Call metadata:
- call_id: {row["call_id"]}
- client: {row["client"]}
- voicebot: {row["voicebot"]}
- state: {row.get("state", "")}
- date: {row.get("date", "")}
- local_call_time: {row.get("local_call_time", "")}
- business_outcome: {row["business_outcome"]}
- qa_evidence: {row.get("qa_evidence", "")}

Transcript:
{row["transcript"]}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e)}


def generate_engineering_ticket_with_gemini(
    client,
    voicebot,
    request_source,
    client_request,
    current_behavior,
    desired_behavior,
    priority,
    related_call_ids,
):
    related_ids_text = ", ".join(related_call_ids) if related_call_ids else "None"

    def offline_engineering_ticket():
        return f"""Title:
Update {voicebot} for {client}: {desired_behavior}

Background:
Request source: {request_source}
Client request: {client_request}

Problem:
{current_behavior}

Requested Change:
{desired_behavior}

Requirements:
- Keep the existing voicebot flow stable unless the requested behavior requires a change.
- Add the new behavior only for eligible conversations and confirmed client-approved scenarios.
- Escalate to a human when the customer disputes the balance, says they already paid, asks for a person, or raises a compliance-sensitive concern.
- Avoid threatening, legal, or pressure-based language.

Acceptance Criteria:
- The bot can handle the requested scenario in a test conversation.
- The bot does not offer unsupported options when eligibility is unclear.
- The bot preserves safe escalation paths.
- TAM can review the updated behavior using related call examples.

Edge Cases:
- Customer is not the right party.
- Customer asks for a human.
- Customer disputes the balance or says they already paid.
- Customer expresses hardship or cannot pay today.

Dependencies / Open Questions:
- Confirm exact eligibility rules with the client.
- Confirm whether any payment method, link, or escalation flow requires engineering integration.
- Confirm rollout scope across clients and voicebots.

Priority:
{priority}

Related Evidence:
Related call IDs: {related_ids_text}
"""

    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if not api_key:
        return offline_engineering_ticket()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are a Technical Account Manager translating a client request into a clear engineering ticket.

Write a developer-ready ticket based on the client request below.

Rules:
- Be specific and actionable.
- Do not invent payment policies, eligibility rules, vendors, or compliance requirements.
- Include open questions when details are missing.
- Make it clear this is a draft ticket for engineering review.
- Keep the ticket concise but complete.

Inputs:
Client: {client}
Voicebot: {voicebot}
Request source: {request_source}
Priority: {priority}
Related call IDs: {related_ids_text}
Client request: {client_request}
Current behavior: {current_behavior}
Desired behavior: {desired_behavior}

Output format:
Title:
Background:
Problem:
Requested Change:
Requirements:
Acceptance Criteria:
Edge Cases:
Dependencies / Open Questions:
Priority:
Related Evidence:
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0},
        )
        return response.text
    except Exception:
        return offline_engineering_ticket()
