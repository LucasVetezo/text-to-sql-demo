"""
Custom evaluation metrics for the text-to-SQL demo.

Three tiers:
  1. Deterministic (no LLM, runs on every query inline):
       sql_valid  — does the SQL parse?
       sql_safe   — no DML/DDL?
       answer_ok  — is the answer non-empty and sensible?

  2. LLM-judge (OpenAI, runs in batch harness only):
       answer_relevance   — does the answer address the question?
       answer_correctness — does the answer match the ground truth?

  3. Aggregate (computed by harness): pass rate, mean latency

Usage from harness:
    from app.evals.metrics import DETERMINISTIC_METRICS, LLM_JUDGE_METRICS
"""

import re
import sqlite3

import mlflow
from mlflow.metrics import make_metric, MetricValue


# ---------------------------------------------------------------------------
# 1. Deterministic scorers — used both inline and in batch evals
# ---------------------------------------------------------------------------


def score_sql_valid(sql: str | None) -> float:
    """Return 1.0 if the SQL is parseable by SQLite EXPLAIN, else 0.0.
    Returns 1.0 (n/a) when no SQL is expected (sentiment / speech)."""
    if not sql or not sql.strip():
        return 1.0
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute(f"EXPLAIN {sql.strip()}")
        conn.close()
        return 1.0
    except sqlite3.Error:
        return 0.0


def score_sql_safe(sql: str | None) -> float:
    """Return 1.0 if the SQL contains no DML/DDL keywords, else 0.0.
    Returns 1.0 (n/a) when no SQL expected."""
    if not sql or not sql.strip():
        return 1.0
    _DML_DDL = re.compile(
        r"\b(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|TRUNCATE|REPLACE|MERGE)\b",
        re.IGNORECASE,
    )
    return 0.0 if _DML_DDL.search(sql) else 1.0


def score_answer_quality(answer: str) -> float:
    """Heuristic answer quality score 0.0–1.0.
    - Empty / error prefix  → 0.0 – 0.2
    - Very short (<30 chars) → 0.4
    - Reasonable (≥30 chars) → 1.0
    """
    if not answer or not answer.strip():
        return 0.0
    a = answer.strip().lower()
    if a.startswith(("error", "i'm sorry", "i cannot", "i don't know", "i am unable")):
        return 0.2
    if len(answer.strip()) < 30:
        return 0.4
    return 1.0


def compute_inline_scores(answer: str, sql_query: str | None) -> dict[str, float]:
    """
    Run all deterministic scorers and return a flat dict ready for
    mlflow.log_metrics(). Called inside invoke_agent on every query.
    """
    return {
        "eval/sql_valid": score_sql_valid(sql_query),
        "eval/sql_safe": score_sql_safe(sql_query),
        "eval/answer_quality": score_answer_quality(answer),
    }


# ---------------------------------------------------------------------------
# 2. MLflow make_metric wrappers — used by mlflow.evaluate() in the harness
# ---------------------------------------------------------------------------


def _sql_valid_eval(predictions, targets, metrics, inputs):
    """MLflow metric: SQL validity score per row."""
    scores = []
    for pred in predictions:
        # predictions may be a dict with 'sql_query' key or a plain string
        if isinstance(pred, dict):
            sql = pred.get("sql_query")
        else:
            sql = None
        scores.append(score_sql_valid(sql))
    return MetricValue(scores=scores, aggregate_results={"mean": sum(scores) / len(scores)})


def _sql_safe_eval(predictions, targets, metrics, inputs):
    """MLflow metric: SQL safety score per row."""
    scores = []
    for pred in predictions:
        if isinstance(pred, dict):
            sql = pred.get("sql_query")
        else:
            sql = None
        scores.append(score_sql_safe(sql))
    return MetricValue(scores=scores, aggregate_results={"mean": sum(scores) / len(scores)})


def _answer_quality_eval(predictions, targets, metrics, inputs):
    """MLflow metric: Heuristic answer quality score per row."""
    scores = []
    for pred in predictions:
        answer = pred.get("answer", "") if isinstance(pred, dict) else str(pred)
        scores.append(score_answer_quality(answer))
    return MetricValue(scores=scores, aggregate_results={"mean": sum(scores) / len(scores)})


def _latency_ok_eval(predictions, targets, metrics, inputs):
    """MLflow metric: 1.0 if latency_ms < 15,000 else 0.0."""
    scores = []
    for pred in predictions:
        latency = pred.get("latency_ms", 0) if isinstance(pred, dict) else 0
        scores.append(1.0 if latency < 15_000 else 0.0)
    return MetricValue(scores=scores, aggregate_results={"mean": sum(scores) / len(scores)})


# mlflow.evaluate()-compatible metric objects
sql_valid_metric = make_metric(
    eval_fn=_sql_valid_eval,
    greater_is_better=True,
    name="sql_valid",
)

sql_safe_metric = make_metric(
    eval_fn=_sql_safe_eval,
    greater_is_better=True,
    name="sql_safe",
)

answer_quality_metric = make_metric(
    eval_fn=_answer_quality_eval,
    greater_is_better=True,
    name="answer_quality",
)

latency_ok_metric = make_metric(
    eval_fn=_latency_ok_eval,
    greater_is_better=True,
    name="latency_ok",
)

# 3. LLM-judge metrics (built-in MLflow GenAI metrics, require OpenAI key)
def get_llm_judge_metrics():
    """Return LLM-as-judge metrics. Imported lazily to avoid slow import at startup."""
    from mlflow.metrics.genai import answer_similarity, answer_relevance

    return [
        answer_relevance(),   # scores how well the answer addresses the question
        answer_similarity(),  # scores semantic similarity to ground_truth
    ]


# Convenience collections for the harness
DETERMINISTIC_METRICS = [sql_valid_metric, sql_safe_metric, answer_quality_metric, latency_ok_metric]
