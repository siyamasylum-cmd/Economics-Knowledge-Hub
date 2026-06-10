from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from bepi.database import get_connection

load_dotenv()


def ensure_brief_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_briefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                brief_type TEXT NOT NULL,
                focus_question TEXT,
                geography TEXT,
                topic TEXT,
                article_ids TEXT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def article_context(articles: list[dict]) -> str:
    parts = []
    for index, article in enumerate(articles, start=1):
        parts.append(
            "\n".join(
                [
                    f"[{index}] {article.get('title', '')}",
                    f"Source: {article.get('source', 'unknown')}",
                    f"Topic: {article.get('topic', 'unknown')} | Geography: {article.get('geography', 'unknown')} | BEPI: {article.get('bepi_signal', 0)}",
                    f"URL: {article.get('url', '')}",
                    f"Summary: {article.get('summary') or article.get('raw_excerpt') or ''}",
                ]
            )
        )
    return "\n\n".join(parts)


def interpret_bepi(score: float) -> str:
    if score >= 35:
        return "The evidence set is strongly positive, with growth, stability, export, investment, or recovery language dominating."
    if score >= 10:
        return "The evidence set is mildly positive, but topic-specific risks still need attention."
    if score <= -35:
        return "The evidence set is strongly negative, with inflation, debt, shortage, labor-market, or macro stress language dominating."
    if score <= -10:
        return "The evidence set is mildly negative, suggesting emerging pressure rather than a clear crisis signal."
    return "The evidence set is mixed or neutral, so the main value is identifying which subtopics are moving differently."


def fallback_brief(articles: list[dict], brief_type: str, focus_question: str, audience: str, geography: str, topic: str) -> str:
    title = focus_question.strip() or f"{brief_type}: {geography} {topic}"
    avg_bepi = sum(float(a.get("bepi_signal") or 0) for a in articles) / max(len(articles), 1)
    lines = [
        f"# {title}",
        "",
        f"**Brief type:** {brief_type}",
        f"**Audience:** {audience}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Evidence base:** {len(articles)} articles",
        f"**Average BEPI signal:** {avg_bepi:.1f}",
        "",
        "## One-minute takeaway",
        "",
        interpret_bepi(avg_bepi),
        "",
        "## Key evidence",
        "",
    ]
    for article in articles:
        lines.extend([
            f"- **{article.get('title', '')}** ({article.get('source', 'unknown')})",
            f"  - Topic: {article.get('topic', 'unknown')} | Geography: {article.get('geography', 'unknown')} | BEPI: {article.get('bepi_signal', 0)}",
            f"  - {article.get('summary') or article.get('raw_excerpt') or 'No summary available.'}",
            f"  - Source: {article.get('url', '')}",
        ])
    lines.extend([
        "",
        "## Bangladesh implications",
        "",
        "- Identify whether the pressure is household-facing, firm-facing, financial-sector-facing, or fiscal.",
        "- Compare local coverage against the global signal before treating it as Bangladesh-specific.",
        "- Track whether the same topic appears repeatedly across different sources.",
        "",
        "## Policy options or decisions",
        "",
        "- Monitor the highest-risk indicator connected to this topic over the next week.",
        "- Separate short-run relief measures from structural reforms.",
        "- Look for distributional effects across income groups, workers, exporters, and small firms.",
        "",
        "## Research opportunities",
        "",
        "- What data would confirm or reject this media signal?",
        "- Which comparable country offers a useful policy benchmark?",
        "- Is the current signal temporary, seasonal, or structural?",
        "",
        "## Source list",
        "",
    ])
    for article in articles:
        lines.append(f"- [{article.get('title', '')}]({article.get('url', '')})")
    return "\n".join(lines)


def generate_brief(articles: list[dict], brief_type: str, focus_question: str, audience: str, geography: str, topic: str) -> str:
    if not articles:
        return "# No brief generated\n\nNo articles were selected."
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_key_here":
        return fallback_brief(articles, brief_type, focus_question, audience, geography, topic)
    prompt = f"""Create a useful Markdown economics intelligence brief.
Use only the supplied article notes. Do not invent facts.

Brief type: {brief_type}
Audience: {audience}
Focus question: {focus_question or 'Find the most important policy and research signal.'}
Geography filter: {geography}
Topic filter: {topic}

Required sections:
# Clear title
## One-minute takeaway
## Key evidence
## Bangladesh implications
## Policy options or decisions
## Risks and uncertainties
## Research opportunities
## Source list

Keep it practical, concrete, and under 900 words.

Articles:
{article_context(articles)}
"""
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25,
            max_tokens=1400,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        return f"<!-- AI generation failed: {exc} -->\n\n" + fallback_brief(articles, brief_type, focus_question, audience, geography, topic)


def save_brief(title: str, brief_type: str, focus_question: str, geography: str, topic: str, article_ids: list[int], content: str) -> int:
    ensure_brief_table()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO policy_briefs(title, brief_type, focus_question, geography, topic, article_ids, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, brief_type, focus_question, geography, topic, json.dumps(article_ids), content),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_recent_briefs(limit: int = 5) -> list[dict]:
    with get_connection() as conn:
        try:
            rows = conn.execute(
                """
                SELECT id, title, brief_type, geography, topic, created_at, content
                FROM policy_briefs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except Exception:
            return []
    return [dict(row) for row in rows]