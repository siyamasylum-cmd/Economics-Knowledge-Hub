from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Single clean import — both functions exist in brief_generator.py
from bepi.brief_generator import generate_policy_brief, generate_brief, save_brief, list_recent_briefs

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "bepi_data/bepi.db"))

SAMPLE_ARTICLE_CANDIDATES = [
    PROJECT_ROOT / "bepi_data" / "sample_articles.csv",
    PROJECT_ROOT / "sample_articles.csv",
]
SAMPLE_HISTORY_CANDIDATES = [
    PROJECT_ROOT / "bepi_data" / "sample_bepi_history.csv",
    PROJECT_ROOT / "sample_bepi_history.csv",
]
SAMPLE_ARTICLES_PATH = next(
    (p for p in SAMPLE_ARTICLE_CANDIDATES if p.exists()), SAMPLE_ARTICLE_CANDIDATES[0]
)
SAMPLE_HISTORY_PATH = next(
    (p for p in SAMPLE_HISTORY_CANDIDATES if p.exists()), SAMPLE_HISTORY_CANDIDATES[0]
)

POLICY_TOPICS = [
    "Inflation", "Exchange Rate", "Trade",
    "Agriculture", "Energy", "Social Protection",
]
POLICY_TOPIC_KEYWORDS = {
    "Inflation":         ["inflation", "price", "prices", "cpi", "food inflation", "cost of living"],
    "Exchange Rate":     ["exchange rate", "currency", "taka", "dollar", "forex", "reserve", "remittance"],
    "Trade":             ["trade", "export", "exports", "import", "imports", "tariff", "shipment"],
    "Agriculture":       ["agriculture", "farm", "farmer", "crop", "rice", "food", "harvest"],
    "Energy":            ["energy", "electricity", "power", "fuel", "gas", "oil", "renewable"],
    "Social Protection": ["social protection", "safety net", "poverty", "welfare", "benefit", "allowance"],
}

TOPIC_EMOJI = {
    "Inflation": "📈",
    "Exchange Rate": "💱",
    "Trade": "🚢",
    "Agriculture": "🌾",
    "Energy": "⚡",
    "Social Protection": "🛡️",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def policy_topic_mask(df: pd.DataFrame, topic: str) -> pd.Series:
    keywords = POLICY_TOPIC_KEYWORDS[topic]
    searchable = (
        df["topic"].fillna("") + " " +
        df["title"].fillna("") + " " +
        df["summary"].fillna("") + " " +
        df["raw_excerpt"].fillna("")
    ).str.lower()
    return searchable.apply(lambda text: any(kw in text for kw in keywords))


def policy_tracker_rows(df: pd.DataFrame) -> list[dict]:
    latest_date = df["article_date"].max()
    if pd.isna(latest_date):
        latest_date = pd.Timestamp.now()
    current_start  = latest_date - pd.Timedelta(days=7)
    previous_start = latest_date - pd.Timedelta(days=14)
    rows = []
    for topic in POLICY_TOPICS:
        topic_df    = df[policy_topic_mask(df, topic)]
        current_df  = topic_df[topic_df["article_date"] >= current_start]
        previous_df = topic_df[
            (topic_df["article_date"] >= previous_start) &
            (topic_df["article_date"] <  current_start)
        ]
        avg_sentiment = current_df["bepi_signal"].mean() if not current_df.empty else 0.0
        previous_avg  = previous_df["bepi_signal"].mean() if not previous_df.empty else None
        if previous_avg is None or pd.isna(previous_avg):
            trend = "→"
        elif avg_sentiment > previous_avg + 2:
            trend = "↑"
        elif avg_sentiment < previous_avg - 2:
            trend = "↓"
        else:
            trend = "→"
        rows.append({
            "": TOPIC_EMOJI.get(topic, ""),
            "Topic": topic,
            "Articles (7d)": int(len(current_df)),
            "Avg BEPI": round(float(avg_sentiment), 1),
            "Trend": trend,
        })
    return rows


def bepi_color(score: float) -> str:
    if score >= 10:
        return "green"
    if score <= -10:
        return "red"
    return "orange"


def sentiment_badge(score: float) -> str:
    if score >= 10:
        return "🟢 Positive"
    if score <= -10:
        return "🔴 Negative"
    return "🟡 Neutral"


# ─── Page config & CSS ────────────────────────────────────────────────────────

st.set_page_config(page_title="Bangladesh Economic Pulse Index", layout="wide", page_icon="📊")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }

    /* Header */
    .bepi-kicker {
        color: #52616f; font-size: 0.8rem; font-weight: 700;
        letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 0.3rem;
    }
    .bepi-title {
        color: #102033; font-size: 2.2rem; font-weight: 760;
        line-height: 1.12; margin: 0;
    }
    .bepi-subtitle {
        color: #5d6b7a; font-size: 0.97rem; line-height: 1.55;
        max-width: 920px; margin-top: 0.6rem;
    }
    .bepi-badge {
        display: inline-block; border: 1px solid #d7dee8; border-radius: 999px;
        color: #334155; background: #f8fafc; padding: 0.25rem 0.65rem;
        margin-right: 0.4rem; margin-top: 0.35rem; font-size: 0.8rem;
    }
    .bepi-divider { margin: 1.2rem 0 1rem; border-top: 1px solid #e6ebf2; }

    /* Article cards */
    .article-card {
        border: 1px solid #e6ebf2; border-radius: 10px;
        padding: 0.85rem 1rem; margin-bottom: 0.65rem;
        background: #fafbfc;
    }
    .article-title { font-weight: 600; font-size: 0.95rem; color: #102033; }
    .article-meta  { font-size: 0.78rem; color: #7a8895; margin-top: 0.2rem; }
    .article-summary { font-size: 0.87rem; color: #344455; margin-top: 0.4rem; }

    /* Policy Lab */
    .policy-section-header {
        font-size: 1rem; font-weight: 700; color: #102033;
        border-left: 4px solid #2563eb; padding-left: 0.6rem;
        margin: 1.4rem 0 0.8rem;
    }
    .tracker-positive { color: #16a34a; font-weight: 600; }
    .tracker-negative { color: #dc2626; font-weight: 600; }
    .tracker-neutral  { color: #d97706; font-weight: 600; }

    /* Brief output */
    .brief-box {
        background: #f8faff; border: 1px solid #dbe8ff;
        border-radius: 10px; padding: 1.2rem 1.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─── Data loading ─────────────────────────────────────────────────────────────

conn = sqlite3.connect(DB_PATH) if DB_PATH.exists() else None
using_sample_data = conn is None

if conn is None:
    if not SAMPLE_ARTICLES_PATH.exists():
        st.warning("Database not found. Run: python -m bepi.database, then python -m bepi.collector")
        st.stop()
    all_df = pd.read_csv(SAMPLE_ARTICLES_PATH)
else:
    base_sql = """
        SELECT a.id, a.title, a.url, a.published_at, a.collected_at, a.summary, a.raw_excerpt,
               a.topic, a.geography, a.bepi_signal, s.name AS source
        FROM articles a
        LEFT JOIN sources s ON s.id = a.source_id
        ORDER BY coalesce(a.published_at, a.collected_at) DESC
    """
    all_df = pd.read_sql_query(base_sql, conn)
    if all_df.empty and SAMPLE_ARTICLES_PATH.exists():
        all_df = pd.read_csv(SAMPLE_ARTICLES_PATH)
        using_sample_data = True

if all_df.empty:
    st.info("No articles yet. Run run_bepi.bat to collect your first batch.")
    if conn is not None:
        conn.close()
    st.stop()

# Normalise columns
all_df["article_date"] = pd.to_datetime(
    all_df["published_at"].fillna(all_df.get("collected_at", pd.NaT)),
    errors="coerce", utc=True,
).dt.tz_convert(None).fillna(pd.Timestamp.now())

all_df["week"]       = all_df["article_date"].dt.to_period("W").dt.start_time
all_df["topic"]      = all_df["topic"].fillna("unclassified")
all_df["geography"]  = all_df["geography"].fillna("unknown")
all_df["bepi_signal"] = pd.to_numeric(all_df["bepi_signal"], errors="coerce").fillna(0)
all_df["source"]     = all_df.get("source", pd.Series(["unknown"] * len(all_df))).fillna("unknown")
all_df["summary"]    = all_df.get("summary", pd.Series([""] * len(all_df))).fillna("")

# History
try:
    if using_sample_data or conn is None:
        history_df = pd.read_csv(SAMPLE_HISTORY_PATH) if SAMPLE_HISTORY_PATH.exists() else pd.DataFrame()
    else:
        history_df = pd.read_sql_query(
            "SELECT period_start, period_end, geography, score, article_count FROM bepi_history ORDER BY period_start",
            conn,
        )
except Exception:
    history_df = pd.DataFrame()

if not history_df.empty:
    history_df["week"]     = pd.to_datetime(history_df["period_start"], errors="coerce")
    history_df["bepi"]     = pd.to_numeric(history_df["score"],         errors="coerce").fillna(0)
    history_df["articles"] = pd.to_numeric(history_df["article_count"], errors="coerce").fillna(0)


# ─── Header ───────────────────────────────────────────────────────────────────

latest_article_date  = all_df["article_date"].max()
latest_article_label = latest_article_date.strftime("%b %d, %Y") if pd.notna(latest_article_date) else "unknown"
data_mode            = "Demo dataset" if using_sample_data else "Live database"
history_rows         = len(history_df) if not history_df.empty else 0

st.markdown(
    f"""
    <div class="bepi-kicker">Bangladesh macroeconomic media monitor</div>
    <h1 class="bepi-title">Bangladesh Economic Pulse Index</h1>
    <div class="bepi-subtitle">
        Weekly media-based pulse score, topic map, article feed, and policy brief workspace
        built from Bangladesh and global economics coverage.
    </div>
    <div>
        <span class="bepi-badge">{data_mode}</span>
        <span class="bepi-badge">Latest: {latest_article_label}</span>
        <span class="bepi-badge">{len(all_df):,} articles</span>
        <span class="bepi-badge">{history_rows} weekly index points</span>
    </div>
    <div class="bepi-divider"></div>
    """,
    unsafe_allow_html=True,
)

if using_sample_data:
    st.info("📦 Demo mode — showing bundled sample data. Run the pipeline locally for live updates.")


# ─── Top metrics ──────────────────────────────────────────────────────────────

bd_df       = all_df[all_df["geography"] == "bangladesh"]
latest_week = all_df["week"].max()
latest_bd   = bd_df[bd_df["week"] == latest_week] if not bd_df.empty else pd.DataFrame()
prev_bd     = bd_df[bd_df["week"] < latest_week]
prev_week   = prev_bd["week"].max() if not prev_bd.empty else None
prev_bd     = bd_df[bd_df["week"] == prev_week] if prev_week is not None else pd.DataFrame()

latest_score  = latest_bd["bepi_signal"].mean() if not latest_bd.empty else bd_df["bepi_signal"].mean()
prev_score    = prev_bd["bepi_signal"].mean() if not prev_bd.empty else None
delta         = None if (prev_score is None or pd.isna(prev_score)) else latest_score - prev_score

mc = st.columns(5)
mc[0].metric("Bangladesh BEPI",    f"{latest_score:.1f}", None if delta is None else f"{delta:+.1f}")
mc[1].metric("Total Articles",     f"{len(all_df):,}")
mc[2].metric("Bangladesh Articles",f"{len(bd_df):,}")
mc[3].metric("Global Articles",    f"{len(all_df[all_df['geography']=='global']):,}")
mc[4].metric("Topics Tracked",     f"{all_df['topic'].nunique():,}")

st.caption("BEPI: −100 (most negative) → +100 (most positive). Measures economics media tone, not official statistics.")


# ─── Tabs ─────────────────────────────────────────────────────────────────────

chart_tab, topics_tab, policy_tab, articles_tab, about_tab = st.tabs([
    "📈 Weekly Pulse",
    "🗂️ Topic Breakdown",
    "🏛️ Policy Lab",
    "📰 Article Feed",
    "ℹ️ About BEPI",
])


# ── Tab 1: Weekly Pulse ───────────────────────────────────────────────────────

with chart_tab:
    if history_df.empty:
        weekly = (
            all_df.groupby(["week", "geography"], as_index=False)
            .agg(bepi=("bepi_signal", "mean"), articles=("id", "count"))
            .sort_values("week")
        )
        st.info("Run `python -m bepi.index_engine` once to persist BEPI history to your database.")
    else:
        weekly = history_df[["week", "geography", "bepi", "articles"]].sort_values("week")

    fig = px.line(
        weekly, x="week", y="bepi", color="geography", markers=True,
        hover_data={"articles": True, "week": True, "bepi": ":.1f"},
        labels={"week": "Week", "bepi": "BEPI score", "geography": "Geography"},
        color_discrete_map={"bangladesh": "#2563eb", "global": "#7c3aed"},
    )
    fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8", line_width=1)
    fig.update_yaxes(range=[-100, 100])
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=30, b=20),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

    export = weekly.copy()
    export["week"] = export["week"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "⬇️ Download Weekly BEPI CSV",
        export.to_csv(index=False).encode("utf-8"),
        file_name="weekly_bepi.csv",
        mime="text/csv",
    )


# ── Tab 2: Topic Breakdown ────────────────────────────────────────────────────

with topics_tab:
    left, right = st.columns(2)
    with left:
        topic_geo = (
            all_df.groupby(["topic", "geography"], as_index=False)
            .agg(bepi=("bepi_signal", "mean"), articles=("id", "count"))
            .sort_values("bepi")
        )
        fig_topic = px.bar(
            topic_geo, x="bepi", y="topic", color="geography", barmode="group",
            hover_data={"articles": True, "bepi": ":.1f"},
            labels={"bepi": "Average BEPI", "topic": "Topic"},
            color_discrete_map={"bangladesh": "#2563eb", "global": "#7c3aed"},
        )
        fig_topic.add_vline(x=0, line_dash="dash", line_color="#94a3b8", line_width=1)
        fig_topic.update_layout(height=520, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_topic, use_container_width=True)

    with right:
        weekly_topic = (
            all_df.groupby(["week", "topic"], as_index=False)
            .agg(articles=("id", "count"), bepi=("bepi_signal", "mean"))
        )
        fig_volume = px.bar(
            weekly_topic, x="week", y="articles", color="topic",
            labels={"week": "Week", "articles": "Article count"},
        )
        fig_volume.update_xaxes(tickformat="%b %d")
        fig_volume.update_layout(height=520, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_volume, use_container_width=True)


# ── Tab 3: Policy Lab ─────────────────────────────────────────────────────────

with policy_tab:
    st.markdown("## 🏛️ Policy Intelligence Lab")
    st.caption("Turn collected articles into structured, evidence-grounded policy briefs.")

    # ── Section 1: Topic Selector ──────────────────────────────────────────────
    st.markdown('<div class="policy-section-header">1 · Topic Selector</div>', unsafe_allow_html=True)

    topic_cols = st.columns([2, 1, 1])
    with topic_cols[0]:
        selected_policy_topic = st.selectbox(
            "Policy topic",
            POLICY_TOPICS,
            format_func=lambda t: f"{TOPIC_EMOJI.get(t, '')} {t}",
        )
    with topic_cols[1]:
        days_window = st.selectbox("Date window", [7, 14, 30, 90], index=1,
                                   format_func=lambda d: f"Last {d} days")
    with topic_cols[2]:
        geo_filter = st.selectbox("Geography", ["all", "bangladesh", "global"], index=1)

    policy_df = all_df[policy_topic_mask(all_df, selected_policy_topic)].copy()
    if geo_filter != "all":
        policy_df = policy_df[policy_df["geography"] == geo_filter]

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_window)
    policy_df = policy_df[policy_df["article_date"] >= cutoff].sort_values("article_date", ascending=False)

    if policy_df.empty:
        st.info(f"No articles found for **{selected_policy_topic}** in the last {days_window} days. Try widening the window or topic.")
    else:
        avg_bepi_topic = policy_df["bepi_signal"].mean()
        m1, m2, m3 = st.columns(3)
        m1.metric("Articles found",    len(policy_df))
        m2.metric("Avg BEPI signal",   f"{avg_bepi_topic:.1f}")
        m3.metric("Sentiment",         sentiment_badge(avg_bepi_topic))

    # ── Section 2: Brief Generator ─────────────────────────────────────────────
    st.markdown('<div class="policy-section-header">2 · Policy Brief Generator</div>', unsafe_allow_html=True)

    if "latest_policy_brief" not in st.session_state:
        st.session_state.latest_policy_brief = ""
        st.session_state.latest_policy_title  = ""

    article_choices = policy_df.head(12) if not policy_df.empty else pd.DataFrame()

    if article_choices.empty:
        st.info("Select a topic with matching articles above to generate a brief.")
    else:
        st.caption(f"Select articles to include (tip: 4–8 gives the best results).")

        selected_article_ids: list[int] = []
        for _, row in article_choices.iterrows():
            row_id = int(row["id"])
            bepi_val = float(row["bepi_signal"])
            badge = sentiment_badge(bepi_val)
            label = f"**{row['title']}**  |  {row['source']}  |  BEPI {bepi_val:.1f}  {badge}"
            # Pre-check first 6
            default_checked = len(selected_article_ids) < 6
            if st.checkbox(label, value=default_checked, key=f"pol_{selected_policy_topic}_{row_id}"):
                selected_article_ids.append(row_id)

        # Show selected count
        if selected_article_ids:
            st.caption(f"✅ {len(selected_article_ids)} articles selected for brief generation.")

        col_gen, col_clear = st.columns([2, 1])
        with col_gen:
            can_generate = len(selected_article_ids) > 0
            generate_clicked = st.button(
                "🔍 Generate Policy Brief",
                type="primary",
                disabled=not can_generate,
                use_container_width=True,
            )
        with col_clear:
            if st.button("🗑️ Clear Brief", use_container_width=True):
                st.session_state.latest_policy_brief = ""
                st.session_state.latest_policy_title  = ""
                st.rerun()

        if generate_clicked and can_generate:
            selected_df = policy_df[policy_df["id"].astype(int).isin(selected_article_ids)]
            records     = selected_df.to_dict(orient="records")
            with st.spinner(f"Generating {selected_policy_topic} policy brief using Groq…"):
                content = generate_policy_brief(records, selected_policy_topic)
            article_ids = [int(r["id"]) for r in records]
            brief_id = None
            if not using_sample_data:
                try:
                    brief_id = save_brief(
                        f"{selected_policy_topic} Policy Brief",
                        "Policy brief",
                        "",
                        geo_filter,
                        selected_policy_topic,
                        article_ids,
                        content,
                    )
                except Exception:
                    pass
            st.session_state.latest_policy_brief = content
            st.session_state.latest_policy_title  = (
                f"{selected_policy_topic.lower().replace(' ', '_')}_brief.md"
            )
            if brief_id:
                st.success(f"✅ Brief generated and saved (ID #{brief_id})")
            else:
                st.success("✅ Brief generated.")

    # Display generated brief
    if st.session_state.latest_policy_brief:
        st.markdown("---")
        st.markdown("#### Generated Brief")
        with st.container():
            st.markdown(
                f'<div class="brief-box">{st.session_state.latest_policy_brief}</div>',
                unsafe_allow_html=True,
            )

        dl_col, copy_col = st.columns(2)
        with dl_col:
            st.download_button(
                "⬇️ Download as Markdown",
                st.session_state.latest_policy_brief.encode("utf-8"),
                file_name=st.session_state.latest_policy_title or "policy_brief.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with copy_col:
            # Copy-to-clipboard via small JS injection
            escaped = st.session_state.latest_policy_brief.replace("`", "\\`").replace("\\", "\\\\")
            st.components.v1.html(
                f"""
                <button onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>this.innerText='✅ Copied!')"
                    style="width:100%;padding:0.5rem;border:1px solid #d1d5db;border-radius:6px;
                           background:#f9fafb;cursor:pointer;font-size:0.9rem;">
                    📋 Copy to Clipboard
                </button>
                """,
                height=45,
            )

    # ── Section 3: Policy Tracker ──────────────────────────────────────────────
    st.markdown('<div class="policy-section-header">3 · Policy Tracker</div>', unsafe_allow_html=True)
    st.caption("Coverage and sentiment across all tracked policy areas in the last 7 days.")

    tracker_rows = policy_tracker_rows(all_df)
    tracker_df   = pd.DataFrame(tracker_rows)

    # Color-code the Trend column
    def style_trend(val):
        if val == "↑":  return "color: #16a34a; font-weight: bold;"
        if val == "↓":  return "color: #dc2626; font-weight: bold;"
        return "color: #d97706; font-weight: bold;"

    def style_bepi(val):
        if val >= 10:   return "color: #16a34a;"
        if val <= -10:  return "color: #dc2626;"
        return "color: #d97706;"

    styled = tracker_df.style \
        .applymap(style_trend,  subset=["Trend"]) \
        .applymap(style_bepi,   subset=["Avg BEPI"]) \
        .format({"Avg BEPI": "{:.1f}"})

    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Quick jump to topic from tracker
    st.caption("Click a topic in the selector above to drill into its articles and generate a brief.")

    # Recent Briefs archive
    if not using_sample_data:
        recent = list_recent_briefs(limit=5)
        if recent:
            st.markdown('<div class="policy-section-header">4 · Recent Briefs Archive</div>', unsafe_allow_html=True)
            for brief in recent:
                with st.expander(f"📄 {brief['title']} — {brief['created_at'][:10]}  ({brief.get('word_count', '?')} words)"):
                    st.markdown(brief["content"])
                    st.download_button(
                        "⬇️ Download",
                        brief["content"].encode("utf-8"),
                        file_name=f"brief_{brief['id']}.md",
                        mime="text/markdown",
                        key=f"dl_brief_{brief['id']}",
                    )


# ── Tab 4: Article Feed ───────────────────────────────────────────────────────

with articles_tab:
    search_col, geo_col, topic_col = st.columns([3, 1, 1])
    with search_col:
        query = st.text_input("🔍 Search", placeholder="inflation, Bangladesh exports, monetary policy…")
    with geo_col:
        geo = st.selectbox("Geography", ["all", "bangladesh", "global"], key="feed_geo")
    with topic_col:
        topic_options = ["all"] + sorted(all_df["topic"].dropna().unique().tolist())
        topic = st.selectbox("Topic", topic_options, key="feed_topic")

    filtered = all_df.copy()
    if geo != "all":
        filtered = filtered[filtered["geography"] == geo]
    if topic != "all":
        filtered = filtered[filtered["topic"] == topic]
    if query:
        q = query.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(q) |
            filtered["summary"].fillna("").str.lower().str.contains(q)
        ]

    st.caption(f"{len(filtered):,} articles match your filters.")

    if filtered.empty:
        st.info("No matching articles. Try adjusting filters.")
    else:
        for _, row in filtered.head(80).iterrows():
            bepi_val = float(row["bepi_signal"])
            badge    = sentiment_badge(bepi_val)
            date_str = row["article_date"].strftime("%b %d, %Y") if pd.notna(row["article_date"]) else ""
            url      = row.get("url", "")
            title    = row.get("title", "Untitled")
            title_md = f"[{title}]({url})" if url else title

            st.markdown(
                f"""<div class="article-card">
                    <div class="article-title">{title_md if not url else ''}</div>
                    <div class="article-meta">
                        {row['source']} &nbsp;·&nbsp; {row['geography']} &nbsp;·&nbsp;
                        {row['topic']} &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp;
                        BEPI {bepi_val:.1f} {badge}
                    </div>
                    <div class="article-summary">{row['summary'][:280] + '…' if len(str(row['summary'])) > 280 else row['summary']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            if url:
                st.markdown(f"[→ Read article]({url})", unsafe_allow_html=False)


# ── Tab 5: About ──────────────────────────────────────────────────────────────

with about_tab:
    st.subheader("Methodology & Limitations")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### How the Score Is Built")
        st.markdown("""
1. Articles collected from 30+ Bangladesh and global economics RSS sources.
2. Text extracted and summarised using AI (Groq / Gemini / Ollama).
3. Each article receives a topic label and geography tag.
4. Positive/negative economics keywords counted in title, summary, and body.
5. Scores topic-weighted and scaled from **−100 to +100**.
6. Weekly BEPI = average score for same geography and week.
        """)
        st.markdown("#### Score Interpretation")
        st.markdown("""
| Score | Meaning |
|-------|---------|
| > +35 | Strongly positive coverage |
| +10 to +35 | Mildly positive |
| −10 to +10 | Mixed / neutral |
| −35 to −10 | Mildly negative |
| < −35 | Strongly negative |
        """)

    with col2:
        st.markdown("#### Source Coverage")
        source_counts = (
            all_df.groupby("source", as_index=False)
            .agg(articles=("id", "count"))
            .sort_values("articles", ascending=False)
        )
        st.dataframe(source_counts, use_container_width=True, hide_index=True)

        st.markdown("#### Limitations")
        st.markdown("""
- Media tone ≠ measured economic performance.
- RSS availability varies by source.
- Keyword scoring is transparent but less nuanced than econometrics.
- Demo mode uses bundled sample data — run pipeline for live index.
        """)

    st.markdown("#### Suggested Citation")
    st.code(
        "Bangladesh Economic Pulse Index (BEPI) — experimental media-based economics intelligence dashboard. "
        "Built with Python, SQLite, Groq AI, and Streamlit.",
        language="text",
    )


# ─── Cleanup ──────────────────────────────────────────────────────────────────

if conn is not None:
    conn.close()
