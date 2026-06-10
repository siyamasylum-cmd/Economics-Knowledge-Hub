from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from bepi.database import get_connection, init_db

POSITIVE_TERMS = {
    "growth": 2.0,
    "grew": 1.5,
    "recovery": 1.5,
    "improve": 1.5,
    "improved": 1.5,
    "strong": 1.2,
    "stable": 1.2,
    "stability": 1.2,
    "investment": 1.4,
    "exports rose": 1.8,
    "export growth": 1.8,
    "remittance": 1.2,
    "surplus": 1.3,
    "productivity": 1.4,
    "jobs added": 1.6,
    "wage growth": 1.4,
}

NEGATIVE_TERMS = {
    "inflation": 1.8,
    "food inflation": 2.2,
    "crisis": 2.0,
    "decline": 1.5,
    "fell": 1.3,
    "fall": 1.3,
    "risk": 1.2,
    "shortage": 1.6,
    "deficit": 1.6,
    "unemployment": 1.8,
    "job losses": 1.8,
    "default": 1.8,
    "non-performing loan": 2.0,
    "debt distress": 2.2,
    "currency pressure": 1.7,
    "reserve pressure": 1.7,
    "poverty": 1.3,
}

TOPIC_WEIGHTS = {
    "inflation": 1.25,
    "monetary policy": 1.15,
    "labor": 1.1,
    "trade": 1.05,
    "banking": 1.15,
    "fiscal policy": 1.1,
    "poverty": 1.1,
    "inequality": 1.0,
    "development": 1.0,
    "general economics": 0.9,
}


def count_term(text: str, term: str) -> int:
    pattern = r"\b" + re.escape(term) + r"\b"
    return len(re.findall(pattern, text))


def score_text(text: str, topic: str | None = None) -> float:
    text_l = re.sub(r"\s+", " ", text.lower())
    positive = sum(weight * count_term(text_l, term) for term, weight in POSITIVE_TERMS.items())
    negative = sum(weight * count_term(text_l, term) for term, weight in NEGATIVE_TERMS.items())

    if positive == 0 and negative == 0:
        return 0.0

    raw = (positive - negative) / (positive + negative)
    weighted = raw * TOPIC_WEIGHTS.get(topic or "general economics", 1.0)
    bounded = max(-1.0, min(1.0, weighted))
    return round(bounded * 100, 1)


def parse_article_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def record_bepi_history() -> int:
    groups: dict[tuple[str, str], list[float]] = {}
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT geography, published_at, collected_at, bepi_signal
            FROM articles
            WHERE bepi_signal IS NOT NULL
            """
        ).fetchall()

        for row in rows:
            article_dt = parse_article_datetime(row["published_at"] or row["collected_at"])
            period_start = (article_dt - timedelta(days=article_dt.weekday())).date().isoformat()
            geography = row["geography"] or "unknown"
            groups.setdefault((period_start, geography), []).append(float(row["bepi_signal"]))

        for (period_start, geography), scores in groups.items():
            start_dt = datetime.fromisoformat(period_start)
            period_end = (start_dt + timedelta(days=6)).date().isoformat()
            score = round(sum(scores) / len(scores), 1)
            conn.execute(
                """
                INSERT INTO bepi_history(period_start, period_end, geography, score, article_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(period_start, period_end, geography)
                DO UPDATE SET
                    score = excluded.score,
                    article_count = excluded.article_count,
                    computed_at = CURRENT_TIMESTAMP
                """,
                (period_start, period_end, geography, score, len(scores)),
            )
        conn.commit()
    print(f"Recorded {len(groups)} weekly BEPI history rows")
    return len(groups)


def compute_scores(recompute_all: bool = True) -> int:
    init_db()
    updated = 0
    where_clause = "" if recompute_all else "WHERE bepi_signal IS NULL"
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, title, body_text, summary, topic
            FROM articles
            {where_clause}
            """
        ).fetchall()
        for row in rows:
            text = " ".join([row["title"] or "", row["summary"] or "", row["body_text"] or ""])
            score = score_text(text, row["topic"])
            conn.execute(
                "UPDATE articles SET sentiment_score = ?, bepi_signal = ? WHERE id = ?",
                (score, score, row["id"]),
            )
            updated += 1
        conn.commit()
    print(f"Computed BEPI signals for {updated} articles")
    record_bepi_history()
    return updated


if __name__ == "__main__":
    compute_scores()
