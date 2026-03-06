"""
Synthetic Credit Card / Loan Application Data Generator
========================================================
Run: python data/synthetic/generate_credit_data.py --rows 500 --seed 42

Generates realistic South African credit application data for Nedbank,
including assessor decline comments written in realistic banking language.
"""

import argparse
import json
import os
import random
import sqlite3
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker("en")  # ZA-specific data handled via custom lists below

# ---------------------------------------------------------------------------
# South African context data
# ---------------------------------------------------------------------------
SA_PROVINCES = [
    "Gauteng", "Western Cape", "KwaZulu-Natal", "Eastern Cape",
    "Limpopo", "Mpumalanga", "North West", "Free State", "Northern Cape",
]

NEDBANK_BRANCHES = {
    "Gauteng": ["Sandton City", "Rosebank", "Pretoria Central", "Midrand", "Soweto"],
    "Western Cape": ["Cape Town CBD", "Claremont", "Stellenbosch", "Paarl"],
    "KwaZulu-Natal": ["Durban CBD", "Umhlanga", "Pietermaritzburg", "Richards Bay"],
    "Eastern Cape": ["Port Elizabeth", "East London", "Mthatha"],
    "Limpopo": ["Polokwane", "Tzaneen"],
    "Mpumalanga": ["Nelspruit", "Witbank"],
    "North West": ["Rustenburg", "Mahikeng"],
    "Free State": ["Bloemfontein", "Welkom"],
    "Northern Cape": ["Kimberley", "Upington"],
}

EMPLOYMENT_STATUSES = ["employed", "self-employed", "unemployed", "retired", "contract"]

LOAN_PURPOSES = ["home", "vehicle", "personal", "education", "business", "debt_consolidation"]

DECLINE_REASONS = {
    "low_credit_score": "Credit score below minimum threshold for product",
    "high_dti": "Debt-to-income ratio exceeds 40% affordability limit",
    "insufficient_income": "Verified income does not meet minimum product requirement",
    "employment_instability": "Less than 3 months at current employer",
    "adverse_credit_history": "Previous defaults or judgements on credit bureau",
    "incomplete_documentation": "Supporting documents not submitted or expired",
    "blacklisted": "Applicant listed under debt review or administration order",
    "age": "Applicant does not meet minimum age requirement",
    "affordability": "Monthly repayment exceeds 30% of nett income",
    "existing_nedbank_arrears": "Existing Nedbank account in arrears",
}

ASSESSOR_TEMPLATES = {
    "low_credit_score": [
        "Applicant's TransUnion credit score of {score} falls below the minimum threshold of 650 required for this product. "
        "History of multiple missed payments on retail accounts noted. Application declined pending score improvement. "
        "Advised applicant to dispute any incorrect bureau entries and reapply after 6 months.",
        "Credit bureau assessment reflects a score of {score} against a minimum requirement of 620. "
        "Two active judgements identified on bureau dating from {year}. "
        "Suggested applicant engage with credit rehabilitation programme before reapplication.",
    ],
    "high_dti": [
        "Verified gross monthly income of R{income:,} against total committed debt obligations of R{debt:,} per month, "
        "resulting in a debt-to-income ratio of {dti:.0f}%. This exceeds Nedbank's maximum affordability threshold of 40%. "
        "Applicant advised to settle existing revolving credit facilities before reapplying.",
        "Income verification confirmed salary of R{income:,} p.m. Existing credit commitments total R{debt:,} p.m. "
        "DTI ratio of {dti:.0f}% is above policy limit. Partial settlement of personal loan recommended to improve eligibility.",
    ],
    "insufficient_income": [
        "Declared income of R{income:,} per annum does not meet the minimum income requirement of R{min_income:,} p.a. "
        "for the requested loan amount of R{loan:,}. No secondary income disclosed. Application cannot proceed at this stage.",
        "Salary slip submitted reflects net monthly income of R{income:,} which is below the floor income of R{min_income:,} "
        "required for this product tier. Applicant directed to a more appropriate product with lower entry requirements.",
    ],
    "adverse_credit_history": [
        "Bureau reflects 3 adverse listings in the past 24 months including a default on an FNB home loan "
        "and two retail account charge-offs. Risk profile is not aligned with product acceptance criteria. "
        "Decline noted with recommendation to engage with NCR-registered debt counsellor.",
        "TransUnion report shows judgement of R{debt:,} granted in {year} and two active adverse listings. "
        "The adverse credit profile presents unacceptable risk exposure. Full settlement of judgement required before reconsideration.",
    ],
}

FALLBACK_COMMENT = (
    "Application reviewed and assessed against Nedbank's credit policy framework. "
    "Based on the overall risk profile including credit bureau data, income verification, "
    "and existing commitments, the application does not meet the minimum criteria at this stage. "
    "Applicant may reapply after 90 days subject to material change in financial circumstances."
)


def generate_assessor_comment(decline_reason: str, row: dict) -> str:
    templates = ASSESSOR_TEMPLATES.get(decline_reason, [FALLBACK_COMMENT])
    template = random.choice(templates)
    try:
        income_monthly = int(row["annual_income"] / 12)
        debt_monthly = int(row["existing_debt"] / 12)
        dti = (debt_monthly / max(income_monthly, 1)) * 100
        return template.format(
            score=row["credit_score"],
            income=income_monthly,
            debt=debt_monthly,
            dti=dti,
            loan=int(row["loan_amount_requested"]),
            min_income=income_monthly + random.randint(5000, 15000),
            year=random.randint(2020, 2024),
        )
    except (KeyError, ValueError):
        return FALLBACK_COMMENT


def generate_record(seed_offset: int = 0) -> dict:
    province = random.choice(SA_PROVINCES)
    branch = random.choice(NEDBANK_BRANCHES[province])
    employment = random.choice(EMPLOYMENT_STATUSES)

    # Income varies by employment type
    if employment == "employed":
        annual_income = random.randint(120_000, 800_000)
    elif employment == "self-employed":
        annual_income = random.randint(80_000, 1_200_000)
    elif employment == "retired":
        annual_income = random.randint(60_000, 300_000)
    elif employment == "contract":
        annual_income = random.randint(100_000, 600_000)
    else:
        annual_income = random.randint(18_000, 80_000)

    credit_score = random.randint(300, 850)
    existing_debt = random.uniform(0, annual_income * 0.6)
    loan_amount = random.randint(5_000, 500_000)
    years_employed = None if employment == "unemployed" else round(random.uniform(0.1, 20), 1)

    # Determine status based on risk factors
    dti = (existing_debt / max(annual_income, 1))
    if credit_score >= 700 and dti < 0.35 and employment in ("employed", "retired"):
        status = random.choices(["approved", "rejected", "pending"], weights=[70, 15, 15])[0]
    elif credit_score >= 580 and dti < 0.45:
        status = random.choices(["approved", "rejected", "pending"], weights=[40, 45, 15])[0]
    else:
        status = random.choices(["approved", "rejected", "pending"], weights=[10, 80, 10])[0]

    # Decline reason and assessor comment
    decline_reason = None
    assessor_comment = None
    if status == "rejected":
        if credit_score < 580:
            decline_reason = "low_credit_score"
        elif dti > 0.45:
            decline_reason = "high_dti"
        elif annual_income < 72_000:
            decline_reason = "insufficient_income"
        elif employment == "unemployed":
            decline_reason = "employment_instability"
        else:
            decline_reason = random.choice(list(DECLINE_REASONS.keys()))
        assessor_comment = generate_assessor_comment(
            decline_reason,
            {"credit_score": credit_score, "annual_income": annual_income,
             "existing_debt": existing_debt, "loan_amount_requested": loan_amount},
        )

    app_date = date.today() - timedelta(days=random.randint(1, 730))

    return {
        "applicant_id": str(fake.uuid4()),
        "name": fake.name(),
        "age": random.randint(18, 65),
        "gender": random.choice(["Male", "Female", "Non-binary", "Prefer not to say"]),
        "annual_income": round(annual_income, 2),
        "credit_score": credit_score,
        "employment_status": employment,
        "employer_name": fake.company() if employment not in ("unemployed", "retired") else None,
        "years_employed": years_employed,
        "existing_debt": round(existing_debt, 2),
        "loan_amount_requested": float(loan_amount),
        "loan_purpose": random.choice(LOAN_PURPOSES),
        "application_status": status,
        "decline_reason": DECLINE_REASONS.get(decline_reason) if decline_reason else None,
        "assessor_comment": assessor_comment,
        "application_date": str(app_date),
        "branch": branch,
        "province": province,
    }


def generate_credit_data(n: int, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    Faker.seed(seed)
    records = [generate_record(i) for i in range(n)]
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic credit application data")
    parser.add_argument("--rows", type=int, default=500, help="Number of records to generate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--output", default="data/seeds/credit_applications.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df = generate_credit_data(args.rows, args.seed)
    df.to_json(args.output, orient="records", indent=2)
    print(f"✅ Generated {len(df)} credit application records → {args.output}")


if __name__ == "__main__":
    main()
