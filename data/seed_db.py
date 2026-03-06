"""
Database Seed Script
====================
Run: python data/seed_db.py

Generates all synthetic datasets and loads them into the SQLite dev database.
Idempotent — safe to re-run (drops and recreates each table).
"""

import os
import sqlite3
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.synthetic.generate_credit_data import generate_credit_data
from data.synthetic.generate_fraud_data import generate_fraud_data
from data.synthetic.generate_social_data import generate_social_data
from data.synthetic.generate_speech_transcripts import generate_speech_transcripts

DB_PATH = os.path.join(os.path.dirname(__file__), "seeds", "dev.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def seed():
    print("\n🌱 Seeding Nedbank AI Demo database...")
    print(f"   Target: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)

    # 1. Credit Applications
    print("📋 Generating credit application data (500 records)...")
    credit_df = generate_credit_data(n=500, seed=42)
    credit_df.to_sql("credit_applications", conn, if_exists="replace", index=True, index_label="id")
    print(f"   ✅ {len(credit_df)} credit applications loaded")

    # 2. Fraud Cases
    print("🚨 Generating fraud case data (300 records)...")
    fraud_df = generate_fraud_data(n=300, seed=42)
    fraud_df.to_sql("fraud_cases", conn, if_exists="replace", index=True, index_label="id")
    print(f"   ✅ {len(fraud_df)} fraud cases loaded")

    # 3. Social Posts
    print("📱 Generating social media post data (400 records)...")
    social_df = generate_social_data(n=400, seed=42)
    social_df.to_sql("social_posts", conn, if_exists="replace", index=True, index_label="id")
    print(f"   ✅ {len(social_df)} social posts loaded")

    # 4. Call Transcripts
    print("🎙️  Generating call centre transcript data (50 records)...")
    speech_df = generate_speech_transcripts(n=50, seed=42)
    speech_df.to_sql("call_transcripts", conn, if_exists="replace", index=True, index_label="id")
    print(f"   ✅ {len(speech_df)} call transcripts loaded")

    # Summary
    cursor = conn.cursor()
    tables = ["credit_applications", "fraud_cases", "social_posts", "call_transcripts"]
    print("\n📊 Database summary:")
    for table in tables:
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"   {table}: {count:,} rows")

    conn.close()
    print(f"\n✅ All done! Database ready at: {DB_PATH}")
    print("   Start the app: make dev\n")


if __name__ == "__main__":
    seed()
