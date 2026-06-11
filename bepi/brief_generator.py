from __future__ import annotations

import json
import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq

from bepi.database import get_connection

load_dotenv()

# ─── Available models (fastest first) ────────────────────────────────────────
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama3-8b-8192",
    "gemma2-9b-it",
]

BRIEF_SECTIONS = [
    "Background",
    "Recent Evidence",
    "Key Indicators",
    "Policy Recommendations",
    "Risks & Uncertainties",
    "Sources",
]

# ─── DB helpers ───────────────────────────────────────────────────────────────

def ensure_brief_table() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS policy_briefs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                brief_type  TEXT NOT NULL,
                focus_question TEXT,
                geography   TEXT,
                topic       TEXT,
                article_ids TEXT,
                content     TEXT NOT NULL,
                word_count  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


# ─── Article formatting ───────────────────────────────────────────────────────

def article_context(articles: list[dict]) -> str:
    """Format a list of article dicts into a clean numbered prompt block."""
    parts = []
    for i, a in enumerate(articles, start=1):
        parts.append(
            "\n".join([
                f"[{i}] {a.get('title', 'Untitled')}",
                f"    Source   : {a.get('source', 'unknown')}",
                f"    Date     : {str(a.get('article_date', a.get('published_at', 'unknown')))[:10]}",
                f"    Topic    : {a.get('topic', 'unknown')} | Geo: {a.get('geography', 'unknown')} | BEPI: {a.get('bepi_signal', 0):.1f}",
                f"    URL      : {a.get('url', '')}",
                f"    Summary  : {a.get('summary') or a.get('raw_excerpt') or 'No summary available.'}",
            ])
        )
    return "\n\n".join(parts)


def interpret_bepi(score: float) -> str:
    if score >= 35:
        return "Strongly positive — growth, stability, export, investment, or recovery language dominates."
    if score >= 10:
        return "Mildly positive — generally stable but topic-specific risks remain."
    if score <= -35:
        return "Strongly negative — inflation, debt, shortage, or macro-stress language dominates."
    if score <= -10:
        return "Mildly negative — emerging pressure signals, not yet a clear crisis."
    return "Mixed/neutral — subtopics are moving in different directions."


# ─── Groq caller (tries models in order) ─────────────────────────────────────

def _call_groq(prompt: str, max_tokens: int = 1500, temperature: float = 0.2) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key in ("your_key_here", ""):
        raise ValueError("No Groq API key set.")
    client = Groq(api_key=api_key)
    last_exc: Exception | None = None
    for model in GROQ_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"All Groq models failed. Last error: {last_exc}")


# ─── Fallback (no API key / API down) ────────────────────────────────────────

def fallback_policy_brief(articles: list[dict], topic: str) -> str:
    avg_bepi = sum(float(a.get("bepi_signal") or 0) for a in articles) / max(len(articles), 1)
    now = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# {topic} Policy Brief",
        f"*Generated: {now} | Articles: {len(articles)} | Avg BEPI: {avg_bepi:.1f}*",
        "",
        "## Background",
        f"This brief synthesizes {len(articles)} collected articles on **{topic.lower()}** in Bangladesh. "
        f"The average BEPI media signal is **{avg_bepi:.1f}** ({interpret_bepi(avg_bepi).lower()})",
        "",
        "## Recent Evidence",
    ]
    for a in articles:
        lines += [
            f"- **{a.get('title', '')}** — *{a.get('source', 'unknown')}*",
            f"  {a.get('summary') or a.get('raw_excerpt') or 'No summary available.'}",
        ]
    lines += [
        "",
        "## Key Indicators",
        f"- Average BEPI signal: **{avg_bepi:.1f}** ({interpret_bepi(avg_bepi)})",
        f"- Evidence base: {len(articles)} articles across "
        f"{len(set(a.get('source','') for a in articles))} sources",
        "- Monitor: prices, external balances, production, household welfare, fiscal exposure.",
        "",
        "## Policy Recommendations",
        "- Determine whether the signal is temporary, seasonal, or structural.",
        "- Cross-check media evidence against official Bangladesh Bank / BBS data.",
        "- Identify the most exposed groups: households, exporters, SMEs, or farmers.",
        "- Prioritise targeted interventions where distributional pressure is clearest.",
        "",
        "## Risks & Uncertainties",
        "- Media tone may lag official data by days or weeks.",
        "- RSS coverage varies — some sources may be over-represented.",
        "- Keyword scoring is transparent but less nuanced than econometric modelling.",
        "",
        "## Sources",
    ]
    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "Untitled")
        lines.append(f"- [{title}]({url})" if url else f"- {title}")
    return "\n".join(lines)


def fallback_brief(
    articles: list[dict],
    brief_type: str,
    focus_question: str,
    audience: str,
    geography: str,
    topic: str,
) -> str:
    """Fallback for the older general memo format."""
    avg_bepi = sum(float(a.get("bepi_signal") or 0) for a in articles) / max(len(articles), 1)
    title = focus_question.strip() or f"{brief_type}: {geography} {topic}"
    lines = [
        f"# {title}",
        f"**Type:** {brief_type} | **Audience:** {audience} | "
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Evidence:** {len(articles)} articles | **Avg BEPI:** {avg_bepi:.1f}",
        "",
        "## One-Minute Takeaway",
        interpret_bepi(avg_bepi),
        "",
        "## Key Evidence",
    ]
    for a in articles:
        lines += [
            f"- **{a.get('title', '')}** ({a.get('source', 'unknown')}, BEPI {a.get('bepi_signal', 0):.1f})",
            f"  {a.get('summary') or a.get('raw_excerpt') or 'No summary.'}",
        ]
    lines += [
        "",
        "## Bangladesh Implications",
        "- Identify whether pressure is household-, firm-, financial-sector-, or fiscal-facing.",
        "- Compare local coverage against global signal before treating as BD-specific.",
        "",
        "## Policy Options",
        "- Monitor the highest-risk indicator over the next week.",
        "- Separate short-run relief from structural reforms.",
        "",
        "## Research Opportunities",
        "- What data would confirm or reject this media signal?",
        "- Which comparable country offers a useful policy benchmark?",
        "",
        "## Source List",
    ]
    for a in articles:
        url = a.get("url", "")
        title = a.get("title", "Untitled")
        lines.append(f"- [{title}]({url})" if url else f"- {title}")
    return "\n".join(lines)


# ─── Main generators ──────────────────────────────────────────────────────────

def generate_policy_brief(articles: list[dict], topic: str) -> str:
    """
    Generate a structured 6-section Bangladesh policy brief.
    Falls back to static template if no Groq key is configured.
    """
    if not articles:
        return "# No brief generated\n\nNo articles were selected."

    try:
        prompt = f"""You are a Bangladesh economics policy analyst. Write a structured policy brief in Markdown.
Use ONLY the supplied article evidence below. Do NOT invent statistics, dates, institutions, or events.

Topic: {topic}

Write exactly these six sections in this order — no extra sections, no preamble:

# {topic} Policy Brief

## Background
2–3 sentences describing the current state of {topic.lower()} in Bangladesh based on the evidence.

## Recent Evidence
Bullet points summarising what the articles say. Quote specific figures only if they appear in the articles.

## Key Indicators
Bullet list of measurable indicators to watch. Only include indicators mentioned in the evidence or clearly flag as "to monitor".

## Policy Recommendations
3–5 concrete, Bangladesh-relevant recommendations. Be specific — name institutions (Bangladesh Bank, NBR, BRAC, etc.) where appropriate.

## Risks & Uncertainties
2–3 risks that could change the outlook. Be honest about media-data limitations.

## Sources
List every article used as: - [Title](URL)

Style: Under 900 words. Clear, direct, no jargon. Written for a Bangladesh policy analyst.

Articles:
{article_context(articles)}
"""
        return _call_groq(prompt, max_tokens=1600, temperature=0.2)

    except Exception as exc:
        return f"<!-- AI generation failed: {exc} -->\n\n" + fallback_policy_brief(articles, topic)


def generate_brief(
    articles: list[dict],
    brief_type: str,
    focus_question: str,
    audience: str,
    geography: str,
    topic: str,
) -> str:
    """Generate a general intelligence memo (used by the older Policy Lab UI)."""
    if not articles:
        return "# No brief generated\n\nNo articles were selected."

    try:
        prompt = f"""Create a practical Markdown economics intelligence brief.
Use only the supplied articles. Do not invent facts.

Brief type: {brief_type}
Audience: {audience}
Focus question: {focus_question or 'Find the most important policy and research signal.'}
Geography: {geography} | Topic: {topic}

Sections (in order):
# [Clear descriptive title]
## One-Minute Takeaway
## Key Evidence
## Bangladesh Implications
## Policy Options or Decisions
## Risks and Uncertainties
## Research Opportunities
## Source List

Under 900 words. Concrete and practical.

Articles:
{article_context(articles)}
"""
        return _call_groq(prompt, max_tokens=1400, temperature=0.25)

    except Exception as exc:
        return f"<!-- AI generation failed: {exc} -->\n\n" + fallback_brief(
            articles, brief_type, focus_question, audience, geography, topic
        )


# ─── Persistence ──────────────────────────────────────────────────────────────

def save_brief(
    title: str,
    brief_type: str,
    focus_question: str,
    geography: str,
    topic: str,
    article_ids: list[int],
    content: str,
) -> int:
    ensure_brief_table()
    word_count = len(content.split())
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO policy_briefs
                (title, brief_type, focus_question, geography, topic, article_ids, content, word_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                brief_type,
                focus_question,
                geography,
                topic,
                json.dumps(article_ids),
                content,
                word_count,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_recent_briefs(limit: int = 5) -> list[dict]:
    with get_connection() as conn:
        try:
            rows = conn.execute(
                """
                SELECT id, title, brief_type, geography, topic, word_count, created_at, content
                FROM policy_briefs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        except Exception:
            return []
    return [dict(row) for row in rows]
