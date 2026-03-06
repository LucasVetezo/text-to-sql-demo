"""
Synthetic Fraud Case Data Generator
=====================================
Run: python data/synthetic/generate_fraud_data.py --rows 300 --seed 42

Generates realistic South African banking fraud investigation cases
with assessor commentary mimicking actual fraud team notes.
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
# Fraud domain data
# ---------------------------------------------------------------------------

FRAUD_TYPES = [
    "card_not_present", "account_takeover", "identity_theft",
    "card_skimming", "phishing", "synthetic_identity",
    "insider_fraud", "first_party_fraud", "money_mule",
]

MERCHANT_CATEGORIES = [
    "online_retail", "travel", "gambling", "electronics",
    "fuel", "groceries", "restaurants", "telecoms", "utilities",
    "luxury_goods", "crypto_exchange", "money_transfer",
]

CHANNELS = ["online", "ATM", "POS", "branch", "mobile_app"]

FRAUD_ASSESSOR_TEMPLATES = {
    "card_not_present": [
        "Transaction flagged by ML model (risk score: {risk:.2f}) for card-not-present activity. "
        "Merchant {merchant} is a known high-risk online category. Card was reported present by customer "
        "at time of transaction — cross-border IP detected from {location}. Customer confirmed did not "
        "authorise transaction. Chargeback initiated; card blocked and replacement dispatched.",

        "CNP transaction of R{amount:,.2f} at {merchant} triggered velocity rule (3rd international "
        "online transaction in 6 hours). Customer contacted via registered mobile — confirmed fraud. "
        "Provisional credit issued. Investigation ongoing with acquiring bank.",
    ],
    "account_takeover": [
        "Unusual login detected from unregistered device at {location} at {time}. "
        "Subsequent high-value transfer of R{amount:,.2f} to new beneficiary initiated within 90 seconds. "
        "Behaviour inconsistent with customer's 18-month transaction pattern. Account frozen, "
        "customer authenticated via branch visit. Full forensic audit of access log underway.",

        "ATO vector: OTP intercepted via SIM-swap executed on {date}. "
        "Attacker added new beneficiary and executed R{amount:,.2f} transfer before detection. "
        "Network provider contacted to reverse SIM-swap. SAPS case number {case} opened. "
        "Funds partially recovered — R{recovered:,.2f} returned to customer.",
    ],
    "identity_theft": [
        "Fraudulent credit application submitted using stolen identity document. "
        "Biometric verification failed on second review — photo mismatch detected. "
        "Original ID holder contacted and confirmed no application submitted. "
        "Application cancelled, credit bureau fraud alert lodged, SAPS case opened.",

        "Social engineering: caller posed as Nedbank security agent, obtained OTP from customer. "
        "R{amount:,.2f} transferred to mule account before flag triggered. "
        "Mule account identified at FNB — collaborative freeze request sent. "
        "R{recovered:,.2f} of R{amount:,.2f} potentially recoverable.",
    ],
    "phishing": [
        "Customer accessed fake Nedbank portal via SMS phishing link. "
        "Entered banking credentials; attacker used credentials to execute R{amount:,.2f} transfer. "
        "Phishing site reported to CERT-SA and domain registrar for takedown. "
        "Customer credentials reset. Awareness communication being drafted for affected segment.",

        "Vishing attack: customer received call from spoofed Nedbank number (+27 11 xxx xxxx). "
        "Provided card details and OTP to attacker. Two transactions totalling R{amount:,.2f} processed. "
        "Both disputed; provisional credit applied. Security awareness flag added to customer profile.",
    ],
    "card_skimming": [
        "Physical skimming device detected at ATM {merchant} during routine inspection on {date}. "
        "Device active for estimated {hours} hours. {count} cards potentially compromised. "
        "All affected accounts identified via ATM transaction logs and proactively blocked. "
        "SAPS and SABRIC notified. ATM taken offline for forensic examination.",
    ],
}

FALLBACK_FRAUD_COMMENT = (
    "Transaction flagged by automated fraud detection system based on anomalous behaviour pattern. "
    "Risk assessment completed; case escalated to Fraud Investigations Unit for further review. "
    "Customer notified and temporary hold placed on account pending outcome of investigation. "
    "Standard chargeback process initiated if applicable."
)

SA_CITIES = [
    "Johannesburg, ZA", "Cape Town, ZA", "Durban, ZA", "Pretoria, ZA",
    "Lagos, NG", "Nairobi, KE", "London, GB", "Dubai, AE",
    "Amsterdam, NL", "New York, US", "Singapore, SG",
]


def generate_fraud_comment(fraud_type: str, amount: float) -> str:
    templates = FRAUD_ASSESSOR_TEMPLATES.get(fraud_type, [FALLBACK_FRAUD_COMMENT])
    template = random.choice(templates)
    try:
        return template.format(
            risk=random.uniform(0.7, 0.99),
            merchant=fake.company(),
            location=random.choice(SA_CITIES),
            amount=amount,
            recovered=amount * random.uniform(0.2, 0.9),
            date=str(date.today() - timedelta(days=random.randint(1, 90))),
            time=f"{random.randint(0,23):02d}:{random.randint(0,59):02d}",
            case=f"CAS-{random.randint(100000, 999999)}/2025",
            hours=random.randint(2, 48),
            count=random.randint(5, 150),
        )
    except (KeyError, ValueError):
        return FALLBACK_FRAUD_COMMENT


def generate_fraud_record() -> dict:
    fraud_type = random.choice(FRAUD_TYPES)
    amount = round(random.uniform(50, 85_000), 2)
    risk_score = round(random.uniform(0.4, 1.0), 3)

    # Higher risk scores more likely to be confirmed
    if risk_score > 0.85:
        fraud_flag = random.choices(
            ["confirmed", "suspected", "cleared"], weights=[70, 25, 5]
        )[0]
    elif risk_score > 0.65:
        fraud_flag = random.choices(
            ["confirmed", "suspected", "cleared"], weights=[30, 55, 15]
        )[0]
    else:
        fraud_flag = random.choices(
            ["confirmed", "suspected", "cleared"], weights=[10, 30, 60]
        )[0]

    case_status = "closed" if fraud_flag == "cleared" else random.choice(
        ["open", "investigating", "closed"]
    )

    tx_date = date.today() - timedelta(days=random.randint(1, 365))

    return {
        "case_id": str(fake.uuid4()),
        "account_number": f"****{random.randint(1000, 9999)}",
        "customer_name": fake.name(),
        "transaction_id": str(fake.uuid4()),
        "transaction_amount": amount,
        "transaction_date": str(tx_date),
        "merchant_name": fake.company(),
        "merchant_category": random.choice(MERCHANT_CATEGORIES),
        "location": random.choice(SA_CITIES),
        "fraud_flag": fraud_flag,
        "risk_score": risk_score,
        "fraud_type": fraud_type if fraud_flag != "cleared" else None,
        "channel": random.choice(CHANNELS),
        "assessor_commentary": generate_fraud_comment(fraud_type, amount)
        if fraud_flag != "cleared"
        else "Transaction reviewed and cleared. No fraudulent activity confirmed. No further action required.",
        "case_status": case_status,
        "reported_date": str(tx_date + timedelta(days=random.randint(0, 5))),
    }


def generate_fraud_data(n: int, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    Faker.seed(seed)
    records = [generate_fraud_record() for _ in range(n)]
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic fraud case data")
    parser.add_argument("--rows", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/seeds/fraud_cases.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df = generate_fraud_data(args.rows, args.seed)
    df.to_json(args.output, orient="records", indent=2)
    print(f"✅ Generated {len(df)} fraud case records → {args.output}")


if __name__ == "__main__":
    main()
