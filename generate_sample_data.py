import random
from datetime import datetime, timedelta

import pandas as pd

CLIENTS = [
    "Atlas Bank",
    "Cedar Credit",
    "Northstar Lending",
    "BrightPath Finance",
    "Riverstone Health",
    "Summit Collections",
    "Pioneer Servicing",
]

VOICEBOTS = ["Hannah", "Maya", "Sofia", "Emma", "Nora", "Lily", "Ava", "Olivia", "Zoe", "Grace"]
STATES = ["CA", "TX", "NY", "FL", "AZ", "NV", "WA"]

# Deliberate demo tradeoff: call_dropped (early_drop) and already-paid mismatch
# (wrong_outcome) are omitted from generation so the sample only surfaces the two
# highest-stakes failure modes — passive under-handling vs. compliance pressure.
# Detection rules for those categories are unchanged; the sample just doesn't exercise them.
OUTCOMES = [
    "payment_collected",
    "promise_to_pay",
    "payment_objection",
    "payment_plan",
    "already_paid",
    "payment_refused",
    "no_answer",
    "transferred_to_human",
]

# Archetype A — passive / under-handling (trips payment_objection detection).
# Customer line must include a trigger term; agent ends weakly with no alternative.
ARCHETYPE_A_PASSIVE_TRANSCRIPTS = [
    "Agent: Can you make a payment today? Customer: I lost my job, I can't pay right now. Agent: Okay. Thank you for your time. Goodbye.",
    "Agent: Are you able to pay today? Customer: I need more time, money's tight. Agent: Understood. Have a good day.",
    "Agent: Can you pay the balance today? Customer: I cannot pay the full amount. Agent: Alright, thank you. Goodbye.",
    "Agent: Can you make a payment today? Customer: Can we do a payment plan? I can't pay it all. Agent: Okay, thank you for letting me know.",
]

# Archetype B — hostile / pressure (trips compliance_risk detection).
# Agent line must include a compliance trigger term.
ARCHETYPE_B_HOSTILE_TRANSCRIPTS = [
    "Agent: You need to pay today. Customer: I can't right now. Agent: You have no choice but to pay now.",
    "Agent: If you do not pay today legal action will begin immediately. Customer: I need more time. Agent: That is not an option.",
    "Agent: Pay now or there will be legal action. Customer: Can I call back? Agent: You have no choice.",
    "Agent: This is your final reminder. Customer: I don't have the money. Agent: You have no choice but to pay now or legal action will follow.",
]

TRANSCRIPT_VARIANTS = {
    "payment_collected": [
        "Agent: Hi, this is Hannah calling about your account. Customer: Yeah, go ahead. Agent: Can you make a payment today? Customer: Yes, I can pay today. Agent: Great, I can help process that payment.",
        "Agent: Good afternoon, I'm calling from your lender. Customer: Hi. Agent: Are you able to make a payment today? Customer: Sure, I have my card ready. Agent: Perfect, let me walk you through that.",
        "Agent: This is Maya with a payment reminder. Customer: Okay. Agent: Would you like to pay your balance today? Customer: Yes, let's do it. Agent: I'll help you complete the payment now.",
        "Agent: Calling about your past-due balance. Customer: I know, sorry about that. Agent: Can we take care of it today? Customer: Yeah I can cover it right now. Agent: Thank you, I'll start the payment.",
    ],
    "promise_to_pay": [
        "Agent: Can you make a payment today? Customer: Not today, but I get paid Friday. Agent: Would Friday work for a payment? Customer: Yes, I can pay Friday. Agent: Great, I'll note a promise to pay.",
        "Agent: I'm reaching out about your balance. Customer: I'm a little short this week. Agent: When would you be able to pay? Customer: Next Tuesday for sure. Agent: I'll schedule that follow-up.",
        "Agent: Hi, this is Nora. Customer: Hi. Agent: Are you able to pay today? Customer: I can do partial on the 15th and the rest at month end. Agent: I'll note that follow-up date.",
        "Agent: Quick reminder about your account. Customer: The full amount is tough this week. Agent: What date works better? Customer: The 28th. Agent: I'll mark a promise to pay for the 28th.",
    ],
    "payment_plan": [
        "Agent: Can you make a payment today? Customer: The full balance is too much for me right now. Agent: I can help review available installment options. Customer: Something monthly would help. Agent: Let me check what's eligible.",
        "Agent: Payment reminder for your account. Customer: I've been trying to call in about splitting this up. Agent: Are you able to pay in full today? Customer: No, I need installments. Agent: I'll look at plan options.",
        "Agent: This is Sofia. Customer: Hi, I wanted to discuss splitting this up. Agent: Can you pay today? Customer: Only if we can spread it out monthly. Agent: I'll review eligibility with you.",
        "Agent: Calling about your past-due balance. Customer: I can do $50 a week maybe? Agent: Would you prefer a structured installment schedule? Customer: Yes please. Agent: I'll walk through the options.",
    ],
    "already_paid": [
        "Agent: Are you able to pay today? Customer: I already paid yesterday through the portal. Agent: Thank you for letting me know. Customer: You should see it by now. Agent: I'll note that on your account.",
        "Agent: This is a balance reminder. Customer: Wait, I paid last week — check your system. Agent: Thank you. Customer: I already paid and I have the confirmation email. Agent: I'll verify payment status.",
        "Agent: Hi, calling about an outstanding balance. Customer: My husband paid it Monday online. Agent: Thanks for confirming. Customer: We already paid. Agent: Okay, I'll verify payment status.",
        "Agent: Quick call about your account. Customer: I submitted payment Friday night. Agent: Thank you. Customer: I already paid — I shouldn't owe anything. Agent: Let me check records.",
    ],
    "no_answer": [
        "No answer.",
        "Ringing... no answer.",
        "Voicemail: You've reached... beep.",
        "No answer after 4 rings.",
    ],
    "transferred_to_human": [
        "Agent: Can you make a payment today? Customer: I want to speak with a person. Agent: I can transfer you to a representative.",
        "Agent: Payment reminder call. Customer: This doesn't sound right — get me a human. Agent: I'll connect you now.",
        "Agent: Are you able to pay today? Customer: I need to talk to someone real about this balance. Agent: Transferring you now.",
        "Agent: Hi, this is Lily. Customer: I've called three times — let me speak to an agent. Agent: One moment while I transfer you.",
    ],
}


def _build_row(rng, call_index, voicebot=None, outcome=None):
    client = rng.choice(CLIENTS)
    bot = voicebot or rng.choice(VOICEBOTS)
    if outcome is None:
        outcome = rng.choices(
            OUTCOMES,
            weights=[22, 18, 12, 8, 10, 8, 12, 10],
            k=1,
        )[0]

    answered = outcome not in ["no_answer"]
    right_party_contact = answered and rng.random() < 0.78
    payment_collected = outcome == "payment_collected"
    failed = outcome == "no_answer"

    duration = 0 if outcome == "no_answer" else rng.randint(45, 420)

    qa_flag = ""
    compliance_flag = False

    if outcome == "payment_objection":
        qa_flag = "payment_objection"
        transcript = rng.choice(ARCHETYPE_A_PASSIVE_TRANSCRIPTS)
    elif outcome == "payment_refused":
        qa_flag = "compliance_risk"
        compliance_flag = True
        transcript = rng.choice(ARCHETYPE_B_HOSTILE_TRANSCRIPTS)
    else:
        transcript = rng.choice(TRANSCRIPT_VARIANTS[outcome])

    date = datetime(2026, 6, 20) + timedelta(days=rng.randint(0, 6))
    hour = rng.randint(8, 20)
    minute = rng.randint(0, 59)

    return {
        "call_id": f"CLL{call_index:04d}",
        "client": client,
        "voicebot": bot,
        "date": date.strftime("%Y-%m-%d"),
        "state": rng.choice(STATES),
        "local_call_time": f"{hour:02d}:{minute:02d}",
        "answered": answered,
        "right_party_contact": right_party_contact,
        "outcome": outcome,
        "payment_collected": payment_collected,
        "failed": failed,
        "call_duration_sec": duration,
        "qa_flag": qa_flag,
        "compliance_flag": compliance_flag,
        "transcript": transcript,
    }


def generate_raw_call_log(n=50, seed=None):
    rng = random.Random(seed)
    rows = []
    call_index = 1

    for bot in VOICEBOTS:
        rows.append(_build_row(rng, call_index, voicebot=bot))
        call_index += 1

    while call_index <= n:
        rows.append(_build_row(rng, call_index))
        call_index += 1

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate_raw_call_log(n=50, seed=42)
    df.to_csv("sample_calls.csv", index=False)
    print("Created sample_calls.csv with", len(df), "rows")
    print(df.head())
