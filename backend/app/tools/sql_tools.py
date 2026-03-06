"""
SQL execution tools for LangGraph agents.

Security:
- All LLM-generated SQL is executed against a READ-ONLY engine.
- A query validator rejects any non-SELECT statements before execution.
- Schema introspection uses a separate whitelisted query — never passes LLM
  output directly to PRAGMA/information_schema without validation.
"""

import re
from typing import Any
import mlflow
from mlflow.entities import SpanType
from langchain_core.tools import tool
from sqlalchemy import text

from app.db.session import readonly_engine


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------

_WRITE_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> None:
    """Raise ValueError if the SQL contains write operations."""
    if _WRITE_PATTERN.search(sql):
        raise ValueError(
            "Write operations (INSERT, UPDATE, DELETE, DROP, etc.) are not permitted. "
            "Only SELECT queries are allowed."
        )


async def _run_sql(sql: str, limit: int = 200) -> list[dict[str, Any]]:
    """Execute validated SQL and return rows as list of dicts."""
    _validate_sql(sql)
    # Wrap in a sub-query to enforce row limit safely
    safe_sql = f"SELECT * FROM ({sql.rstrip(';')}) AS _q LIMIT {limit}"
    async with readonly_engine.connect() as conn:
        result = await conn.execute(text(safe_sql))
        rows = result.fetchall()
        cols = list(result.keys())
    return [dict(zip(cols, row)) for row in rows]


# ---------------------------------------------------------------------------
# Credit Application Tools
# ---------------------------------------------------------------------------


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="get_credit_schema")
async def get_credit_schema() -> str:
    """
    Return the schema of the credit_applications table.
    Use this FIRST before writing any SQL query to understand the available columns.
    """
    schema = """
    Table: credit_applications
    Columns:
      id                  INTEGER   Primary key
      applicant_id        TEXT      UUID unique identifier
      name                TEXT      Applicant full name
      age                 INTEGER   Age in years
      gender              TEXT      Gender (Male/Female/Non-binary/Other)
      annual_income       REAL      Annual income in ZAR
      credit_score        INTEGER   Credit bureau score (300–850)
      employment_status   TEXT      (employed / self-employed / unemployed / retired)
      employer_name       TEXT      Name of employer (nullable)
      years_employed      REAL      Years at current employer (nullable)
      existing_debt       REAL      Total existing debt in ZAR
      loan_amount_requested REAL    Loan amount applied for in ZAR
      loan_purpose        TEXT      Purpose (home / vehicle / personal / education / business)
      application_status  TEXT      (approved / rejected / pending)
      decline_reason      TEXT      Short decline code (nullable)
      assessor_comment    TEXT      Detailed assessor narrative (nullable)
      application_date    TEXT      ISO date string (YYYY-MM-DD)
      branch              TEXT      Nedbank branch name
      province            TEXT      South African province

    Useful filters:
      - Filter by application_status = 'rejected' to analyse declines
      - Use credit_score ranges: Poor(<580), Fair(580-669), Good(670-739), Very Good(740-799), Exceptional(800+)
      - Annual income and existing_debt together indicate debt-to-income ratio
    """
    return schema.strip()


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="execute_credit_sql")
async def execute_credit_sql(sql: str) -> str:
    """
    Execute a SELECT SQL query against the credit_applications table.
    Returns results as a formatted markdown table.
    
    Args:
        sql: A valid SELECT SQL query against the credit_applications table.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results."
        cols = list(rows[0].keys())
        header = " | ".join(cols)
        separator = " | ".join(["---"] * len(cols))
        data_rows = [" | ".join(str(r.get(c, "")) for c in cols) for r in rows]
        return f"| {header} |\n| {separator} |\n" + "\n".join(f"| {r} |" for r in data_rows)
    except ValueError as e:
        return f"⛔ Security error: {e}"
    except Exception as e:
        return f"❌ SQL error: {e}"


# ---------------------------------------------------------------------------
# Fraud Case Tools
# ---------------------------------------------------------------------------


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="get_fraud_schema")
async def get_fraud_schema() -> str:
    """
    Return the schema of the fraud_cases table.
    Use this FIRST before writing any SQL query to understand the available columns.
    """
    schema = """
    Table: fraud_cases
    Columns:
      id                  INTEGER   Primary key
      case_id             TEXT      UUID unique identifier
      account_number      TEXT      Masked account number
      customer_name       TEXT      Customer full name
      transaction_id      TEXT      UUID of the flagged transaction
      transaction_amount  REAL      ZAR amount
      transaction_date    TEXT      ISO date string (YYYY-MM-DD)
      merchant_name       TEXT      Merchant name
      merchant_category   TEXT      MCC category (e.g. retail / travel / online / gambling)
      location            TEXT      City, Country
      fraud_flag          TEXT      (confirmed / suspected / cleared)
      risk_score          REAL      ML model risk score 0.0–1.0 (>0.8 = high risk)
      fraud_type          TEXT      (card_not_present / account_takeover / identity_theft / etc.)
      channel             TEXT      Transaction channel (online / ATM / POS / branch)
      assessor_commentary TEXT      Detailed investigation notes
      case_status         TEXT      (open / investigating / closed)
      reported_date       TEXT      ISO date string (YYYY-MM-DD)

    Useful filters:
      - fraud_flag = 'confirmed' for proven fraud
      - risk_score > 0.8 for high-risk transactions
      - GROUP BY fraud_type or channel for pattern analysis
    """
    return schema.strip()


@tool
@mlflow.trace(span_type=SpanType.TOOL, name="execute_fraud_sql")
async def execute_fraud_sql(sql: str) -> str:
    """
    Execute a SELECT SQL query against the fraud_cases table.
    Returns results as a formatted markdown table.
    
    Args:
        sql: A valid SELECT SQL query against the fraud_cases table.
    """
    try:
        rows = await _run_sql(sql)
        if not rows:
            return "Query returned no results."
        cols = list(rows[0].keys())
        header = " | ".join(cols)
        separator = " | ".join(["---"] * len(cols))
        data_rows = [" | ".join(str(r.get(c, "")) for c in cols) for r in rows]
        return f"| {header} |\n| {separator} |\n" + "\n".join(f"| {r} |" for r in data_rows)
    except ValueError as e:
        return f"⛔ Security error: {e}"
    except Exception as e:
        return f"❌ SQL error: {e}"
