from __future__ import annotations

import os
import re
from dotenv import load_dotenv
from groq import Groq

from bepi.database import get_connection, init_db

load_dotenv()

TOPIC_KEYWORDS = {
    "inflation": ["inflation", "price", "cpi", "cost of living"],
    "monetary policy": ["interest rate", "central bank", "monetary", "policy rate"],
    "labor": ["jobs", "wage", "employment", "unemployment", "workers"],
    "trade": ["export", "import", "tariff", "trade", "shipment"],
    "poverty": ["poverty", "poor", "safety net", "social protection"],
    "inequality": ["inequality", "gini", "distribution", "wealth gap"],
    "development": ["development", "growth", "infrastructure", "productivity"],
    "fiscal policy": ["budget", "tax", "subsidy", "deficit", "public finance"],
    "banking": ["bank", "loan", "credit", "deposit", "npl"],
}


def classify_topic(text: str) -> str:
    text_l = text.lower()
    scores = {
        topic: sum(1 for word in words if word in text_l)
        for topic, words in TOPIC_KEYWORDS.items()
    }
    best_topic, best_score = max(scores.items(), key=lambda item: item[1])
    return best_topic if best_score else "general economics"


def fallback_summary(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "No article text was available for summarization."
    return text[:700] + ("..." if len(text) > 700 else "")


def summarize_with_groq(title: str, text: str) -> str:
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or key == "your_key_here":
        return fallback_summary(text)

    client = Groq(api_key=key)
    prompt = f"""Summarize this economics article for an undergraduate researcher.
Return 3 concise bullets: core claim, evidence/data, and why it matters.

Title: {title}

Article text:
{text[:6000]}
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"AI summary failed, using fallback. Reason: {exc}\n\n{fallback_summary(text)}"


def analyze(limit: int | None = None) -> int:
    init_db()
    processed = 0
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, body_text, raw_excerpt
            FROM articles
            WHERE summary IS NULL OR topic IS NULL
            ORDER BY collected_at DESC
            """ + (" LIMIT ?" if limit else ""),
            (() if limit is None else (limit,)),
        ).fetchall()

        for row in rows:
            text = row["body_text"] or row["raw_excerpt"] or ""
            topic = classify_topic(f"{row['title']} {text}")
            summary = summarize_with_groq(row["title"], text)
            conn.execute(
                "UPDATE articles SET summary = ?, topic = ? WHERE id = ?",
                (summary, topic, row["id"]),
            )
            processed += 1
        conn.commit()
    print(f"Analyzed {processed} articles")
    return processed


if __name__ == "__main__":
    analyze()

