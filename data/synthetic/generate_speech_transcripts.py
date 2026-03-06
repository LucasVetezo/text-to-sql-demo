"""
Synthetic Call Centre Transcript Generator
===========================================
Run: python data/synthetic/generate_speech_transcripts.py --rows 50 --seed 42

Generates realistic multi-turn customer support call transcripts
between Nedbank agents and customers (primarily about credit applications).
Includes pain points, CX scores, and resolution status.
"""

import argparse
import json
import os
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker("en")

# ---------------------------------------------------------------------------
# Call transcript templates (multi-turn dialogue)
# ---------------------------------------------------------------------------

CALL_REASONS = [
    "credit_application_status",
    "loan_decline_appeal",
    "credit_limit_increase",
    "application_documents",
    "repayment_arrangement",
    "fraud_dispute",
    "general_credit_query",
]

AGENT_NAMES = [
    "Thandi Nkosi", "Sipho Dlamini", "Ayanda Mokoena", "Priya Pillay",
    "Johan van der Berg", "Fatima Osman", "Lethabo Sithole", "Roxanne Adams",
]

TRANSCRIPTS = {
    "credit_application_status": {
        "resolved": """
AGENT: Good afternoon, thank you for calling Nedbank, you've reached the credit department. My name is {agent}, how may I assist you today?

CUSTOMER: Hi {agent}, thank you. I applied for a personal loan about two weeks ago and I still haven't heard anything. I've been checking the online portal but it just says pending.

AGENT: I completely understand your frustration, and I apologise for the delay. I'd like to help you today. May I please get your ID number and account number to pull up your application?

CUSTOMER: Yes, sure. My ID number is [REDACTED] and my account is [REDACTED].

AGENT: Thank you. I can see your application here. It looks like it was received on the {date} and it's currently with our credit assessment team. I can see there's a note here requesting an updated payslip — specifically the most recent three months.

CUSTOMER: Oh! Nobody told me that. I submitted one payslip when I applied.

AGENT: I sincerely apologise for the lack of communication on that — you should have received an SMS or email notification. That's something we need to improve. What I'd like to do right now is note that you've called and create an urgent request for the assessor to contact you within 24 hours. I can also give you the direct email address where you can upload those payslips immediately.

CUSTOMER: Okay, that would be helpful. I just wish someone had told me sooner — I've been stressing about this for two weeks.

AGENT: Absolutely understandable, and your feedback is valid. You should not have had to call us to find out this information. I'm noting this on your account. The email for document submission is credit.documents@nedbank.co.za. Once they receive your payslips, processing typically takes 3-5 business days.

CUSTOMER: Alright, I'll send them through today. Thank you for clarifying.

AGENT: You're welcome. Is there anything else I can help you with today?

CUSTOMER: No, that's it. Thanks.

AGENT: Thank you for banking with Nedbank. I hope we can get your application finalised quickly. Have a great afternoon.
""",
        "escalated": """
AGENT: Good morning, Nedbank credit department, {agent} speaking. How can I help?

CUSTOMER: Finally! I've been on hold for 47 minutes. This is absolutely ridiculous. I applied for a home loan and nobody can tell me what's happening.

AGENT: I sincerely apologise for the wait time, that's not the experience we want you to have. Let me look into your application immediately. Can I get your ID and reference number?

CUSTOMER: ID is [REDACTED]. Reference is {ref}. I've called 4 times in 3 weeks and every time someone tells me different information.

AGENT: That's very concerning and I apologise. Let me look at the notes on your file... I can see the application was received on {date}. There have been two requests for documents and I can see you've submitted them. The issue seems to be that your application has been assigned to three different assessors due to internal team changes.

CUSTOMER: This is exactly the problem. Do you know how stressful it is to be trying to buy a house and your bank can't get its act together?

AGENT: You're absolutely right, and I'm not going to make excuses. What I'm going to do is escalate this to my team manager right now who can assign a dedicated assessor and get you a final decision within 48 hours. I'm also flagging this as a complaint so it goes into our formal tracking system.

CUSTOMER: I want that in writing. Can you send me an email confirming what you just said?

AGENT: Absolutely, I'll send that to your registered email address within the next 30 minutes. And you'll receive a direct callback from a senior assessor by close of business tomorrow.

CUSTOMER: Fine. I hope this time someone actually follows through.

AGENT: I understand your frustration completely. You have my word that I will personally follow up. Thank you for your patience.
""",
    },
    "loan_decline_appeal": {
        "resolved": """
AGENT: Nedbank credit department, {agent} speaking, good afternoon.

CUSTOMER: Hi, I received a letter saying my personal loan was declined. I'm quite confused because I have a good credit record and a stable job.

AGENT: I'm sorry to hear you were declined. I'd be happy to explain the decision and discuss your options. May I pull up your application?

CUSTOMER: Please. ID: [REDACTED].

AGENT: Thank you. I can see your application here. The decline was based on your current debt-to-income ratio — your existing commitments plus the new repayment would take your DTI above our 40% affordability threshold.

CUSTOMER: What does that mean exactly? Nobody explained this in the letter.

AGENT: You're right that the letter doesn't provide enough detail — that's feedback I'll pass on. Essentially, we look at all your current monthly debt repayments against your net income. In your case, adding this loan would mean you're committing more than 40% of your take-home pay to debt, which is our policy limit to ensure you can still meet other living expenses.

CUSTOMER: So if I paid off my one credit card first, would that help?

AGENT: Yes, absolutely. If you reduce your existing revolving credit, your DTI ratio would improve. I can run a quick calculation — if you were to close the credit card account and confirm that with a settlement letter, your DTI would drop to approximately {dti}%, which would likely put you within our criteria.

CUSTOMER: That's really helpful. Why don't they just tell us this in the decline letter?

AGENT: That's a very valid point and I will raise it formally. You deserve to understand exactly why and what to do to improve your position. I'm going to make a note on your file that you may reapply in 60 days after settling the credit card, and I'll flag this for a priority review.

CUSTOMER: Okay, I can work with that. Thank you for explaining it properly.

AGENT: Absolutely. Is there anything else I can assist with?
""",
    },
    "fraud_dispute": {
        "resolved": """
AGENT: Nedbank fraud and disputes, {agent} speaking.

CUSTOMER: Hi, I need to report a fraudulent transaction on my account. I just checked my banking app and there's a debit of R8,500 from some online store that I've never heard of.

AGENT: I'm sorry to hear that — let's get this sorted for you right away. Can you confirm your account number and the last four digits of your card?

CUSTOMER: Account is [REDACTED], card ends in {card}.

AGENT: Thank you. I can see that transaction. It was processed 2 hours ago at an online merchant. I'm going to block your card immediately to prevent any further transactions. You'll receive a notification now.

CUSTOMER: Yes, I can see the notification. Oh good. But what about the R8,500?

AGENT: I'll initiate a dispute on that transaction now. Because you're reporting this within 24 hours, we'll apply a provisional credit to your account within 1-2 business days while we investigate with the merchant's bank.

CUSTOMER: So I'll get the money back while you investigate?

AGENT: Yes, that's correct — you'll have the provisional credit while the investigation runs, which typically takes 5-10 business days. If the dispute is confirmed, the credit becomes permanent. I'll also order a replacement card which will arrive in 3-5 business days.

CUSTOMER: That's a relief. Thank you for being so quick about it.

AGENT: Of course. We take fraud very seriously. I'm also noting that you should check for any other unusual transactions over the past week. Is there anything else?

CUSTOMER: No, that covers it. You've been very helpful.

AGENT: Thank you. Please keep monitoring your accounts and don't hesitate to call back. Stay safe.
""",
    },
    "general_credit_query": {
        "abandoned": """
AGENT: Good morning, Nedbank credit queries, {agent} speaking.

CUSTOMER: Morning. I want to know what credit products are available and what I need to qualify.

AGENT: Good morning! I can help with that. We have personal loans, home loans, vehicle finance and credit cards. Which one were you interested in?

CUSTOMER: I'm thinking about a personal loan but I want to understand the requirements first before I apply.

AGENT: Of course. For a personal loan, you'd generally need a minimum monthly income of R3,500, a valid South African ID, and a credit score above 600. Are you currently employed?

CUSTOMER: Yes, I'm employed. Look, can you just send me a link to the full requirements page? I don't want to go through the whole list now.

AGENT: Absolutely. I can send you our credit criteria guide to your registered email address, or I can direct you to nedbank.co.za/personal-loans. Would you like me to—

CUSTOMER: [Call disconnects]

AGENT: Hello? Hello? It seems the call dropped. I'll send the guide to the customer's registered email as a follow-up action.
""",
    },
}


def get_transcript(call_reason: str, resolution_status: str) -> str:
    reason_templates = TRANSCRIPTS.get(call_reason, TRANSCRIPTS["general_credit_query"])
    # Try to get the right resolution, fall back to any available
    template = reason_templates.get(
        resolution_status,
        next(iter(reason_templates.values()))
    )
    agent = random.choice(AGENT_NAMES)
    return template.format(
        agent=agent.split()[0],  # First name only in dialogue
        date=str(date.today() - timedelta(days=random.randint(1, 60))),
        ref=f"NB-{random.randint(100000, 999999)}",
        card=str(random.randint(1000, 9999)),
        dti=round(random.uniform(28, 39), 1),
    ).strip()


CX_SCORE_MAP = {
    "resolved": lambda: round(random.uniform(5.5, 10.0), 1),
    "escalated": lambda: round(random.uniform(3.0, 6.5), 1),
    "abandoned": lambda: round(random.uniform(1.0, 4.5), 1),
}

PAIN_POINTS_MAP = {
    "resolved": ["Long initial wait times", "Poor proactive communication"],
    "escalated": [
        "Inconsistent information across agents",
        "Excessive hold times",
        "Multiple handoffs without context transfer",
        "Application assigned to multiple assessors",
    ],
    "abandoned": ["Technical difficulties on client side", "Agent unable to retain customer"],
}


def generate_transcript_record() -> dict:
    call_reason = random.choice(CALL_REASONS)
    resolution = random.choices(
        ["resolved", "escalated", "abandoned"],
        weights=[60, 30, 10]
    )[0]

    agent = random.choice(AGENT_NAMES)
    duration = {
        "resolved": random.randint(300, 900),
        "escalated": random.randint(900, 2400),
        "abandoned": random.randint(60, 600),
    }[resolution]

    transcript = get_transcript(call_reason, resolution)
    pain_points = PAIN_POINTS_MAP.get(resolution, [])
    cx_score = CX_SCORE_MAP.get(resolution, lambda: 5.0)()

    call_date = date.today() - timedelta(days=random.randint(1, 90))

    return {
        "call_id": str(fake.uuid4()),
        "call_date": str(call_date),
        "duration_seconds": duration,
        "agent_name": agent,
        "customer_name": fake.name(),
        "call_reason": call_reason.replace("_", " ").title(),
        "transcript_text": transcript,
        "pain_points": json.dumps(pain_points),
        "cx_score": cx_score,
        "resolution_status": resolution,
        "audio_file": None,   # Placeholder — real audio would be stored here
    }


def generate_speech_transcripts(n: int, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    Faker.seed(seed)
    records = [generate_transcript_record() for _ in range(n)]
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic call centre transcripts")
    parser.add_argument("--rows", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/seeds/call_transcripts.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df = generate_speech_transcripts(args.rows, args.seed)
    df.to_json(args.output, orient="records", indent=2)

    summary = df["resolution_status"].value_counts()
    avg_cx = df["cx_score"].mean()
    print(f"✅ Generated {len(df)} call transcripts → {args.output}")
    print(f"   Resolution: {dict(summary)}")
    print(f"   Average CX score: {avg_cx:.1f}/10")


if __name__ == "__main__":
    main()
