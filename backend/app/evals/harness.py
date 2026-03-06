#!/usr/bin/env python3
"""
Batch evaluation harness for the text-to-SQL demo.

Runs golden Q&A pairs through the live FastAPI backend, scores each response
with deterministic and (optionally) LLM-judge metrics, then logs everything
to the MLflow experiment as a dedicated eval run.

Usage:
    # Basic (deterministic metrics only — fast, no extra OpenAI cost)
    python -m app.evals.harness --backend http://localhost:8000

    # With LLM-judge metrics (answer_relevance, answer_similarity via GPT-4o)
    python -m app.evals.harness --backend http://localhost:8000 --judge

    # Restrict to one use case
    python -m app.evals.harness --use-case credit

    # As a make target
    make eval
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow running from project root: python -m app.evals.harness
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # backend/

import httpx
import mlflow
import pandas as pd

from app.config import settings
from app.evals.dataset import ALL_CASES, get_cases_for
from app.evals.metrics import (
    DETERMINISTIC_METRICS,
    compute_inline_scores,
    score_sql_valid,
    score_sql_safe,
    score_answer_quality,
)


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def call_backend(client: httpx.Client, backend_url: str, endpoint: str, query: str) -> dict:
    """POST the query to the backend and return the parsed response dict."""
    url = backend_url.rstrip("/") + endpoint
    try:
        resp = client.post(url, json={"query": query}, timeout=60.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        return {"answer": f"HTTP error {e.response.status_code}: {e.response.text}", "sql_query": None, "latency_ms": 0}
    except Exception as e:
        return {"answer": f"Request failed: {e}", "sql_query": None, "latency_ms": 0}


def score_case(response: dict, expected_sql_contains: str) -> dict[str, float]:
    """Run all deterministic scorers on a single response."""
    answer = response.get("answer", "")
    sql = response.get("sql_query")
    latency = response.get("latency_ms", 0)

    scores = {
        "sql_valid": score_sql_valid(sql),
        "sql_safe": score_sql_safe(sql),
        "answer_quality": score_answer_quality(answer),
        "latency_ok": 1.0 if latency < 15_000 else 0.0,
    }

    # Extra check: does the SQL mention expected tables/columns?
    if expected_sql_contains and sql:
        keywords = [k.strip() for k in expected_sql_contains.split(",") if k.strip()]
        if keywords:
            hits = sum(1 for kw in keywords if kw.lower() in sql.lower())
            scores["sql_keyword_coverage"] = hits / len(keywords)
    else:
        scores["sql_keyword_coverage"] = 1.0  # n/a → pass

    return scores


def run_llm_judge(cases_df: pd.DataFrame, predictions: list[str]) -> pd.DataFrame | None:
    """Use mlflow.evaluate() with LLM-judge metrics on pre-collected predictions."""
    try:
        from mlflow.metrics.genai import answer_relevance, answer_similarity

        judge_df = cases_df[["inputs", "targets"]].copy()
        judge_df["predictions"] = predictions

        with mlflow.start_run(nested=True, run_name="llm-judge") as judge_run:
            result = mlflow.evaluate(
                data=judge_df,
                predictions="predictions",
                targets="targets",
                extra_metrics=[answer_relevance(), answer_similarity()],
                evaluators="default",
            )
            return result.tables.get("eval_results_table")
    except Exception as e:
        print(f"  ⚠  LLM judge failed: {e}", file=sys.stderr)
        return None


def run_eval(backend_url: str, use_case: str | None, run_judge: bool) -> None:
    cases = get_cases_for(use_case) if use_case else ALL_CASES
    if not cases:
        print(f"No cases found for use_case={use_case!r}", file=sys.stderr)
        sys.exit(1)

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    run_name = f"eval-{'all' if not use_case else use_case}-{datetime.now():%Y%m%d-%H%M}"
    print(f"\n🔬 Running {len(cases)} eval cases → MLflow run: {run_name}\n")

    rows = []
    all_scores: dict[str, list[float]] = {}
    predictions_for_judge: list[str] = []

    with httpx.Client() as client:
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.set_tag("eval_type", "batch")
            mlflow.set_tag("use_case_filter", use_case or "all")
            mlflow.set_tag("backend_url", backend_url)
            mlflow.log_param("total_cases", len(cases))
            mlflow.log_param("llm_judge", str(run_judge))

            for i, case in enumerate(cases, 1):
                query = case["query"]
                endpoint = case["endpoint"]
                ground_truth = case["ground_truth"]
                expected_keywords = ",".join(case.get("expected_sql_contains", []))

                print(f"  [{i:02d}/{len(cases):02d}] {endpoint}  ›  {query[:60]}…")

                t0 = time.perf_counter()
                response = call_backend(client, backend_url, endpoint, query)
                wall_latency_ms = (time.perf_counter() - t0) * 1000

                answer = response.get("answer", "")
                sql = response.get("sql_query")
                backend_latency = response.get("latency_ms") or wall_latency_ms

                scores = score_case(response, expected_keywords)

                for k, v in scores.items():
                    all_scores.setdefault(k, []).append(v)

                predictions_for_judge.append(answer)

                row = {
                    "case_id": i,
                    "use_case": endpoint.split("/")[2],
                    "query": query,
                    "answer": answer[:300],
                    "sql_query": (sql or "")[:300],
                    "latency_ms": round(backend_latency, 1),
                    "wall_latency_ms": round(wall_latency_ms, 1),
                    **scores,
                }
                rows.append(row)

                status = "✓" if all(v >= 0.8 for v in scores.values()) else "✗"
                print(f"         {status}  sql_valid={scores['sql_valid']:.0f}  sql_safe={scores['sql_safe']:.0f}  answer_quality={scores['answer_quality']:.1f}  latency={backend_latency:.0f}ms\n")

            # --- Aggregate metrics ---
            for metric_name, values in all_scores.items():
                mlflow.log_metric(f"mean/{metric_name}", sum(values) / len(values))

            total_pass = sum(
                1 for r in rows
                if r["sql_valid"] == 1.0
                and r["sql_safe"] == 1.0
                and r["answer_quality"] >= 0.8
                and r["latency_ok"] == 1.0
            )
            pass_rate = total_pass / len(rows)
            mlflow.log_metric("pass_rate", pass_rate)
            mlflow.log_metric("mean_latency_ms", sum(r["latency_ms"] for r in rows) / len(rows))

            # --- Per-case table artifact ---
            results_df = pd.DataFrame(rows)
            artifact_path = Path("/tmp") / f"{run_name}.csv"
            results_df.to_csv(artifact_path, index=False)
            mlflow.log_artifact(str(artifact_path), artifact_path="eval_results")

            # Log the table for MLflow UI table view
            mlflow.log_table(data=results_df, artifact_file="eval_results/results.json")

            # --- LLM judge (optional) ---
            if run_judge:
                print("  🤖 Running LLM judge metrics (answer_relevance, answer_similarity)…")
                cases_df = pd.DataFrame(
                    [{"inputs": c["query"], "targets": c["ground_truth"]} for c in cases]
                )
                run_llm_judge(cases_df, predictions_for_judge)

            print(f"\n✅ Eval complete — pass_rate={pass_rate:.1%}  ({total_pass}/{len(rows)} passed)")
            print(f"   MLflow run ID : {run.info.run_id}")
            print(f"   MLflow UI     : {settings.mlflow_tracking_uri}/#/experiments")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Run batch evals against the text-to-SQL backend")
    parser.add_argument(
        "--backend",
        default="http://localhost:8000",
        help="Base URL of the FastAPI backend (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--use-case",
        choices=["credit", "fraud", "sentiment"],
        default=None,
        help="Restrict eval to a single use case (default: all)",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        default=False,
        help="Also run LLM-judge metrics — costs OpenAI tokens, adds ~1 min",
    )
    args = parser.parse_args()
    run_eval(backend_url=args.backend, use_case=args.use_case, run_judge=args.judge)


if __name__ == "__main__":
    main()
