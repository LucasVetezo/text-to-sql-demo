"""
Synthetic Social Media Post Generator (Nedbank — X / LinkedIn)
================================================================
Run: python data/synthetic/generate_social_data.py --rows 400 --seed 42

Generates realistic social posts about Nedbank from South African social media
users, covering credit, fraud, service, app, and fees topics.
"""

import argparse
import os
import random
from datetime import date, timedelta

import pandas as pd
from faker import Faker

fake = Faker("en")

# ---------------------------------------------------------------------------
# Post templates by topic and sentiment
# ---------------------------------------------------------------------------

POSTS = {
    "credit": {
        "negative": [
            "Applied for a personal loan at @Nedbank 3 weeks ago and still no feedback. "
            "Their online portal shows 'pending' since day 1. This is unacceptable. #NedBankFail",
            "Nedbank declined my home loan application with zero explanation. "
            "No call, no email — just a generic letter. My credit score is 720! "
            "Moving to @StandardBankSA 😤",
            "The credit assessment process at Nedbank is an absolute joke. "
            "They ask for the same documents 3 times and still lose them. "
            "I've been waiting 6 weeks for a simple credit card upgrade.",
            "Nedbank told me I earn too little for a R30k loan but approved my colleague "
            "with the same salary at Absa. Something doesn't add up. #discrimination",
            "Just got declined for a Nedbank vehicle finance. My salary is R45k p.m., "
            "no debt, credit score 780. Their system is broken. 🚗❌",
        ],
        "neutral": [
            "Nedbank credit application process takes about 5-7 business days "
            "based on my experience. Make sure you have all your payslips ready beforehand.",
            "Anyone know what Nedbank's minimum income requirement is for a personal loan? "
            "Website is not very clear on this.",
            "Applied for a Nedbank credit card last week. Still waiting but the online "
            "portal at least shows progress. Will update when I hear back.",
        ],
        "positive": [
            "Got approved for a Nedbank home loan in 4 days! The process was smooth "
            "and my dedicated banker kept me updated throughout. Highly recommend! 🏠✅",
            "Nedbank's credit assessment was thorough but fair. Declined initially but "
            "they gave me a clear reason and told me exactly what to fix. Reapplied 3 months "
            "later and got approved. Appreciate the transparency! 👏",
            "Just got my Nedbank Amex Platinum approved! Amazing limit and the "
            "application was entirely digital — no branch visit needed. "
            "#NedBank #CreditCard",
        ],
    },
    "fraud": {
        "negative": [
            "Someone hacked my Nedbank account and transferred R18k. "
            "Called the fraud line — 45 minute hold time! "
            "By the time I got through, the money was gone. @Nedbank sort this out! 🚨",
            "Nedbank's fraud detection is non-existent. R5k went off my card "
            "at some random merchant in Dubai while I was physically in Joburg. "
            "Where is the real-time monitoring?",
            "Received a phishing SMS from a number spoofing Nedbank today. "
            "Reported it to the bank — they said 'we'll look into it'. "
            "Meanwhile they're still sending these to thousands of customers. 😤",
        ],
        "neutral": [
            "Nedbank froze my account as a precaution after suspicious activity. "
            "Had to go to a branch to verify. Inconvenient but I understand the security concern.",
            "Got a notification about a suspicious transaction from Nedbank. "
            "Turned out to be my normal grocery shop with a new merchant name. "
            "False alarm but at least they're watching.",
        ],
        "positive": [
            "Huge shoutout to @Nedbank fraud team — caught a R12k CNP fraud "
            "before I even noticed it and provisionally credited my account same day. "
            "That's world-class fraud protection! 🙌",
            "Nedbank called me within 2 minutes of a suspicious attempt on my card. "
            "Blocked it immediately. Exactly the proactive protection I expect from my bank. ✅",
        ],
    },
    "service": {
        "negative": [
            "Spent 1.5 hours on hold with Nedbank call centre today. "
            "The IVR kept disconnecting me. "
            "Is the self-service app supposed to replace actual human service? 😡",
            "Branch queues at Nedbank {branch} are absolutely insane. "
            "Waited 2 hours just to update my details. Please hire more staff.",
            "My Nedbank relationship manager has changed 3 times in 6 months. "
            "I have to re-explain my situation every single time. "
            "No continuity whatsoever. #PoorCustomerService",
            "Nedbank's credit department does not return calls. "
            "I've left 4 voicemails in 2 weeks. Someone answer the phone! 📞❌",
        ],
        "neutral": [
            "Mixed experience at Nedbank today. Long wait but the consultant who "
            "eventually helped me was knowledgeable and efficient.",
            "Nedbank's contact centre is usually responsive but today seems unusually busy. "
            "Might be a system issue.",
        ],
        "positive": [
            "Nedbank Sandton City branch set the bar. In and out in 15 minutes, "
            "consultant was warm and professional. Great service Nedbank! 👏",
            "Shoutout to {name} at Nedbank Rosebank — went above and beyond to help "
            "me sort out my credit application documents. "
            "More bankers like this please! 🌟",
        ],
    },
    "app": {
        "negative": [
            "Nedbank Money app crashed again right when I needed to approve a payment. "
            "Third time this week. "
            "@Nedbank when are you fixing this? #NedBankMoney",
            "The biometric login on Nedbank Money is awful. "
            "Asks me to enter my PIN even when Face ID is enabled. "
            "Other bank apps don't have this problem.",
            "Nedbank's app doesn't allow me to upload documents for my loan application. "
            "Forces you to go to a branch. In 2026. Come on! 📱❌",
        ],
        "neutral": [
            "Nedbank Money app update is out. Seems slightly faster but "
            "the credit section UI is still confusing.",
            "Anyone else getting OTP delays on the Nedbank app? "
            "Taking 3+ minutes to receive.",
        ],
        "positive": [
            "Impressed with the new Nedbank Money app update. "
            "Credit application status tracking is now real-time. "
            "Finally a bank that listens! 📱✅",
            "Applied for a credit facility entirely through the Nedbank app. "
            "Zero branch visits, instant decision. "
            "This is how banking should work. #NedBank #DigitalBanking",
        ],
    },
    "fees": {
        "negative": [
            "Nedbank increased my monthly account fees by 12% with 30 days notice. "
            "No loyalty discount for 8-year customers. Time to switch. 💸",
            "The international transaction fees at Nedbank are highway robbery. "
            "2.75% + R65 per transaction. Meanwhile other banks charge way less.",
            "Got charged a R195 service fee for using a human teller. "
            "Nedbank wants you to self-service but then charges you if you actually need help?",
        ],
        "neutral": [
            "Nedbank fee structure has changed a lot since I joined. "
            "Need to compare against other banks at this point.",
            "Does anyone know if Nedbank charges for credit application processing? "
            "Reading the fine print now...",
        ],
        "positive": [
            "Nedbank Savvy Bundle is still one of the best value account packages. "
            "Free card swipes and decent app — can't complain at R79/month.",
            "Good to see Nedbank didn't increase transactional fees this year "
            "unlike some other big 4 banks. Appreciated! 💚",
        ],
    },
}

PLATFORMS = ["X", "LinkedIn"]

# LinkedIn posts tend to be longer and more professional
LINKEDIN_PREFIXES = [
    "Sharing my recent banking experience: ",
    "As a finance professional, I feel compelled to share: ",
    "Customer experience insight: ",
    "Open letter to Nedbank leadership: ",
    "Reflecting on digital banking in SA: ",
    "The state of credit accessibility in South Africa — ",
]


def generate_post(topic: str, sentiment: str, platform: str) -> str:
    templates = POSTS.get(topic, {}).get(sentiment, [])
    if not templates:
        return f"Sharing thoughts about Nedbank's {topic} services."

    post = random.choice(templates)
    # Fill any template placeholders
    post = post.replace("{branch}", random.choice(["Sandton", "Rosebank", "Cape Town CBD"]))
    post = post.replace("{name}", fake.first_name())

    # LinkedIn posts get a professional prefix
    if platform == "LinkedIn" and random.random() < 0.6:
        post = random.choice(LINKEDIN_PREFIXES) + post.lower()

    return post


def sentiment_score_from_label(label: str) -> float:
    if label == "positive":
        return round(random.uniform(0.35, 1.0), 3)
    elif label == "neutral":
        return round(random.uniform(-0.15, 0.35), 3)
    else:
        return round(random.uniform(-1.0, -0.25), 3)


def generate_social_record() -> dict:
    platform = random.choices(["X", "LinkedIn"], weights=[65, 35])[0]
    topic = random.choices(
        list(POSTS.keys()), weights=[35, 20, 25, 12, 8]
    )[0]

    # Negative sentiment is more prevalent on social media (negativity bias)
    sentiment = random.choices(
        ["negative", "neutral", "positive"], weights=[50, 25, 25]
    )[0]

    post_date = date.today() - timedelta(days=random.randint(1, 180))

    likes = 0
    shares = 0
    if sentiment == "negative":
        likes = random.randint(0, 850)
        shares = random.randint(0, 200)
    elif sentiment == "positive":
        likes = random.randint(0, 400)
        shares = random.randint(0, 80)
    else:
        likes = random.randint(0, 150)
        shares = random.randint(0, 30)

    return {
        "post_id": str(fake.uuid4()),
        "platform": platform,
        "author_handle": f"@{fake.user_name()}" if platform == "X" else fake.name(),
        "post_text": generate_post(topic, sentiment, platform),
        "post_date": str(post_date),
        "sentiment_label": sentiment,
        "sentiment_score": sentiment_score_from_label(sentiment),
        "topic": topic,
        "likes": likes,
        "shares": shares,
        "language": "en",
    }


def generate_social_data(n: int, seed: int = 42) -> pd.DataFrame:
    random.seed(seed)
    Faker.seed(seed)
    records = [generate_social_record() for _ in range(n)]
    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic social media post data")
    parser.add_argument("--rows", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="data/seeds/social_posts.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df = generate_social_data(args.rows, args.seed)
    df.to_json(args.output, orient="records", indent=2)

    # Print a quick sentiment summary
    summary = df["sentiment_label"].value_counts()
    print(f"✅ Generated {len(df)} social posts → {args.output}")
    print(f"   Sentiment: {dict(summary)}")


if __name__ == "__main__":
    main()
