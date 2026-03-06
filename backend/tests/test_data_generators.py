"""
Tests for synthetic data generators.
Validates schema, row counts, and reproducibility.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import pytest
import pandas as pd

from data.synthetic.generate_credit_data import generate_credit_data
from data.synthetic.generate_fraud_data import generate_fraud_data
from data.synthetic.generate_social_data import generate_social_data
from data.synthetic.generate_speech_transcripts import generate_speech_transcripts


# ---------------------------------------------------------------------------
# Credit Data Tests
# ---------------------------------------------------------------------------

class TestCreditDataGenerator:
    def test_row_count(self):
        df = generate_credit_data(n=100, seed=42)
        assert len(df) == 100

    def test_reproducible(self):
        df1 = generate_credit_data(n=50, seed=42)
        df2 = generate_credit_data(n=50, seed=42)
        assert df1["applicant_id"].tolist() == df2["applicant_id"].tolist()

    def test_different_seeds_differ(self):
        df1 = generate_credit_data(n=50, seed=42)
        df2 = generate_credit_data(n=50, seed=99)
        assert df1["applicant_id"].tolist() != df2["applicant_id"].tolist()

    def test_required_columns(self):
        df = generate_credit_data(n=10, seed=42)
        required = [
            "applicant_id", "name", "annual_income", "credit_score",
            "employment_status", "loan_amount_requested", "application_status",
            "application_date", "province",
        ]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_application_status_values(self):
        df = generate_credit_data(n=200, seed=42)
        valid = {"approved", "rejected", "pending"}
        assert set(df["application_status"].unique()).issubset(valid)

    def test_rejected_have_comments(self):
        df = generate_credit_data(n=200, seed=42)
        rejected = df[df["application_status"] == "rejected"]
        # Most rejected applications should have assessor comments
        assert rejected["assessor_comment"].notna().mean() > 0.8

    def test_credit_score_range(self):
        df = generate_credit_data(n=200, seed=42)
        assert df["credit_score"].between(300, 850).all()

    def test_no_duplicate_applicant_ids(self):
        df = generate_credit_data(n=200, seed=42)
        assert df["applicant_id"].nunique() == len(df)


# ---------------------------------------------------------------------------
# Fraud Data Tests
# ---------------------------------------------------------------------------

class TestFraudDataGenerator:
    def test_row_count(self):
        df = generate_fraud_data(n=50, seed=42)
        assert len(df) == 50

    def test_required_columns(self):
        df = generate_fraud_data(n=10, seed=42)
        required = [
            "case_id", "transaction_amount", "fraud_flag", "risk_score",
            "case_status", "channel", "reported_date",
        ]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_risk_score_range(self):
        df = generate_fraud_data(n=100, seed=42)
        assert df["risk_score"].between(0.0, 1.0).all()

    def test_fraud_flag_values(self):
        df = generate_fraud_data(n=100, seed=42)
        valid = {"confirmed", "suspected", "cleared"}
        assert set(df["fraud_flag"].unique()).issubset(valid)

    def test_high_risk_scores_correlate_with_confirmed(self):
        df = generate_fraud_data(n=200, seed=42)
        high_risk = df[df["risk_score"] > 0.85]
        confirmed_rate = (high_risk["fraud_flag"] == "confirmed").mean()
        assert confirmed_rate > 0.4, "High risk scores should mostly be confirmed fraud"


# ---------------------------------------------------------------------------
# Social Data Tests
# ---------------------------------------------------------------------------

class TestSocialDataGenerator:
    def test_row_count(self):
        df = generate_social_data(n=100, seed=42)
        assert len(df) == 100

    def test_sentiment_distribution(self):
        df = generate_social_data(n=500, seed=42)
        # Negative should dominate (negativity bias in social media)
        pcts = df["sentiment_label"].value_counts(normalize=True)
        assert pcts.get("negative", 0) > 0.3

    def test_platforms(self):
        df = generate_social_data(n=200, seed=42)
        assert set(df["platform"].unique()).issubset({"X", "LinkedIn"})

    def test_sentiment_score_range(self):
        df = generate_social_data(n=200, seed=42)
        assert df["sentiment_score"].between(-1.0, 1.0).all()

    def test_topics_present(self):
        df = generate_social_data(n=200, seed=42)
        expected_topics = {"credit", "fraud", "service", "app", "fees"}
        assert expected_topics.issubset(set(df["topic"].unique()))


# ---------------------------------------------------------------------------
# Speech Transcript Tests
# ---------------------------------------------------------------------------

class TestSpeechTranscriptGenerator:
    def test_row_count(self):
        df = generate_speech_transcripts(n=20, seed=42)
        assert len(df) == 20

    def test_transcript_not_empty(self):
        df = generate_speech_transcripts(n=10, seed=42)
        assert df["transcript_text"].str.len().min() > 100

    def test_cx_score_range(self):
        df = generate_speech_transcripts(n=30, seed=42)
        assert df["cx_score"].between(1, 10).all()

    def test_resolution_status_values(self):
        df = generate_speech_transcripts(n=30, seed=42)
        valid = {"resolved", "escalated", "abandoned"}
        assert set(df["resolution_status"].unique()).issubset(valid)
