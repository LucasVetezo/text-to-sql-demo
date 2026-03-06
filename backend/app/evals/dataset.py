"""
Golden evaluation dataset for the text-to-SQL demo.

Each entry represents one test case for a use case endpoint. The harness
sends each query to the live backend and scores the response against:
  - ground_truth: used by LLM-judge metrics (answer_similarity, answer_relevance)
  - expected_sql_contains: deterministic check that SQL mentions required tables/columns
  - endpoint: which FastAPI endpoint to call

Keep ground truths approximate — they describe WHAT the answer should address,
not the exact string. LLM judges score semantic similarity, not exact match.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Credit SQL golden cases
# ---------------------------------------------------------------------------

CREDIT_CASES: list[dict[str, Any]] = [
    {
        "query": "How many credit applications were approved versus rejected?",
        "ground_truth": "The answer should compare the count of approved applications to rejected ones, providing both numbers and optionally a percentage split.",
        "expected_sql_contains": ["credit_applications", "status"],
        "endpoint": "/api/credit/query",
    },
    {
        "query": "What are the top 3 most common decline reasons?",
        "ground_truth": "The answer should list the three most frequent decline reasons with their counts or percentages.",
        "expected_sql_contains": ["decline_reason", "COUNT"],
        "endpoint": "/api/credit/query",
    },
    {
        "query": "What is the average credit score of approved applicants?",
        "ground_truth": "The answer should state the mean credit score for applicants whose application status is approved.",
        "expected_sql_contains": ["credit_score", "AVG", "approved"],
        "endpoint": "/api/credit/query",
    },
    {
        "query": "Which province has the highest rejection rate?",
        "ground_truth": "The answer should name a South African province and explain it has the highest proportion of declined applications.",
        "expected_sql_contains": ["province", "credit_applications"],
        "endpoint": "/api/credit/query",
    },
    {
        "query": "What is the average loan amount requested by employment status?",
        "ground_truth": "The answer should show average loan amounts broken down by employment categories such as employed, self-employed, and unemployed.",
        "expected_sql_contains": ["loan_amount", "employment_status", "AVG"],
        "endpoint": "/api/credit/query",
    },
    {
        "query": "Show me the 5 most recent credit applications with their status.",
        "ground_truth": "The answer should list five recent credit applications showing their application ID, applicant name or details, and whether they were approved or rejected.",
        "expected_sql_contains": ["credit_applications", "LIMIT"],
        "endpoint": "/api/credit/query",
    },
]

# ---------------------------------------------------------------------------
# Fraud SQL golden cases
# ---------------------------------------------------------------------------

FRAUD_CASES: list[dict[str, Any]] = [
    {
        "query": "How many fraudulent transactions were detected last month?",
        "ground_truth": "The answer should give a count of transactions flagged as fraudulent with a time reference.",
        "expected_sql_contains": ["fraud_transactions", "is_fraud"],
        "endpoint": "/api/fraud/query",
    },
    {
        "query": "What is the average transaction amount for fraudulent versus legitimate transactions?",
        "ground_truth": "The answer should compare the mean transaction amount for fraud cases against non-fraud cases.",
        "expected_sql_contains": ["amount", "is_fraud", "AVG"],
        "endpoint": "/api/fraud/query",
    },
    {
        "query": "Which merchant category has the most fraudulent transactions?",
        "ground_truth": "The answer should name a merchant category (e.g. online retail, ATM, fuel) with the highest count of fraud.",
        "expected_sql_contains": ["merchant_category", "is_fraud", "COUNT"],
        "endpoint": "/api/fraud/query",
    },
    {
        "query": "What percentage of transactions flagged by our model were actually fraudulent?",
        "ground_truth": "The answer should state the precision or true-positive rate — how many model-flagged transactions were confirmed fraud.",
        "expected_sql_contains": ["fraud_transactions", "model_flagged"],
        "endpoint": "/api/fraud/query",
    },
    {
        "query": "Show me the top 5 highest-value fraudulent transactions.",
        "ground_truth": "The answer should list five transactions with the largest amounts where is_fraud is true.",
        "expected_sql_contains": ["amount", "is_fraud", "ORDER BY", "LIMIT"],
        "endpoint": "/api/fraud/query",
    },
]

# ---------------------------------------------------------------------------
# Sentiment golden cases
# ---------------------------------------------------------------------------

SENTIMENT_CASES: list[dict[str, Any]] = [
    {
        "query": "What is the overall sentiment about Nedbank on social media this week?",
        "ground_truth": "The answer should summarise the balance of positive, neutral, and negative mentions and provide a general sentiment direction.",
        "expected_sql_contains": [],  # Agent uses mock/DB fetch, not raw SQL
        "endpoint": "/api/sentiment/query",
    },
    {
        "query": "What are customers most unhappy about?",
        "ground_truth": "The answer should identify the main themes or topics driving negative sentiment, such as service delays, fees, or app issues.",
        "expected_sql_contains": [],
        "endpoint": "/api/sentiment/query",
    },
    {
        "query": "Summarise the positive feedback from the last 7 days.",
        "ground_truth": "The answer should describe the positive topics customers are mentioning, such as good service or new features.",
        "expected_sql_contains": [],
        "endpoint": "/api/sentiment/query",
    },
]

# ---------------------------------------------------------------------------
# Combined flat list — used by the harness
# ---------------------------------------------------------------------------

ALL_CASES: list[dict[str, Any]] = CREDIT_CASES + FRAUD_CASES + SENTIMENT_CASES


def get_cases_for(use_case: str) -> list[dict[str, Any]]:
    """Return golden cases for a specific use case key."""
    mapping = {
        "credit": CREDIT_CASES,
        "fraud": FRAUD_CASES,
        "sentiment": SENTIMENT_CASES,
    }
    return mapping.get(use_case, [])


def as_dataframe(cases: list[dict[str, Any]] | None = None):
    """Return cases as a pandas DataFrame with columns expected by mlflow.evaluate()."""
    import pandas as pd

    rows = cases if cases is not None else ALL_CASES
    return pd.DataFrame(
        [
            {
                "inputs": c["query"],
                "targets": c["ground_truth"],   # used by LLM-judge as reference
                "endpoint": c["endpoint"],
                "expected_sql_contains": ",".join(c["expected_sql_contains"]),
            }
            for c in rows
        ]
    )
