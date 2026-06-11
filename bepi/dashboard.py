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

from bepi.brief_generator import generate_brief, list_recent_briefs, save_brief

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
SAMPLE_ARTICLES_PATH = next((path for path in SAMPLE_ARTICLE_CANDIDATES if path.exists()), SAMPLE_ARTICLE_CANDIDATES[0])
SAMPLE_HISTORY_PATH = next((path for path in SAMPLE_HISTORY_CANDIDATES if path.exists()), SAMPLE_HISTORY_CANDIDATES[0])

st.set_page_config(page_title="Economics Knowledge Hub", layout="wide")
st.title("Economics Knowledge Hub")

conn = sqlite3.connect(DB_PATH) if DB_PATH.exists() else None
using_sample_data = conn is None

if conn is None:
    if not SAMPLE_ARTICLES_PATH.exists():
        st.warning("Database not found yet. Run: python -m bepi.database, then python -m bepi.collector")
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
    st.info("No articles yet. Double-click run_bepi.bat to collect your first batch.")
    if conn is not None:
        conn.close()
    st.stop()

if using_sample_data:
    st.info("Showing bundled demo data. Run the collector locally or configure hosted collection for live updates.")

all_df["article_date"] = pd.to_datetime(
    all_df["published_at"].fillna(all_df["collected_at"]), errors="coerce", utc=True
).dt.tz_convert(None)
all_df["article_date"] = all_df["article_date"].fillna(pd.Timestamp.now())
all_df["week"] = all_df["article_date"].dt.to_period("W").dt.start_time
all_df["topic"] = all_df["topic"].fillna("unclassified")
all_df["geography"] = all_df["geography"].fillna("unknown")
all_df["bepi_signal"] = pd.to_numeric(all_df["bepi_signal"], errors="coerce").fillna(0)

try:
    if using_sample_data or conn is None:
        history_df = pd.read_csv(SAMPLE_HISTORY_PATH) if SAMPLE_HISTORY_PATH.exists() else pd.DataFrame()
    else:
        history_df = pd.read_sql_query(
            """
            SELECT period_start, period_end, geography, score, article_count, computed_at
            FROM bepi_history
            ORDER BY period_start
            """,
            conn,
        )
except Exception:
    history_df = pd.DataFrame()

if not history_df.empty:
    history_df["week"] = pd.to_datetime(history_df["period_start"], errors="coerce")
    history_df["bepi"] = pd.to_numeric(history_df["score"], errors="coerce").fillna(0)
    history_df["articles"] = pd.to_numeric(history_df["article_count"], errors="coerce").fillna(0)

st.subheader("Bangladesh Economic Pulse Index")
metric_cols = st.columns(4)

bd_df = all_df[all_df["geography"] == "bangladesh"]
latest_week = all_df["week"].max()
latest_bd = bd_df[bd_df["week"] == latest_week] if not bd_df.empty else pd.DataFrame()
previous_bd = bd_df[bd_df["week"] < latest_week]
previous_week = previous_bd["week"].max() if not previous_bd.empty else None
previous_bd = bd_df[bd_df["week"] == previous_week] if previous_week is not None else pd.DataFrame()

latest_score = latest_bd["bepi_signal"].mean() if not latest_bd.empty else bd_df["bepi_signal"].mean()
previous_score = previous_bd["bepi_signal"].mean() if not previous_bd.empty else None
delta = None if previous_score is None or pd.isna(previous_score) else latest_score - previous_score

metric_cols[0].metric("Bangladesh BEPI", f"{latest_score:.1f}", None if delta is None else f"{delta:+.1f}")
metric_cols[1].metric("Articles", f"{len(all_df):,}")
metric_cols[2].metric("Bangladesh Articles", f"{len(bd_df):,}")
metric_cols[3].metric("Topics Tracked", f"{all_df['topic'].nunique():,}")

st.caption("BEPI is a media-based pulse score from -100 to +100. Positive means more growth/stability language; negative means more inflation, crisis, debt, labor-market, or shortage pressure.")

chart_tab, topics_tab, policy_tab, articles_tab = st.tabs([
    "Weekly Pulse",
    "Topic Breakdown",
    "Policy Lab",
    "Article Feed",
])

with chart_tab:
    if history_df.empty:
        weekly = (
            all_df.groupby(["week", "geography"], as_index=False)
            .agg(bepi=("bepi_signal", "mean"), articles=("id", "count"))
            .sort_values("week")
        )
        st.info("Run `python -m bepi.index_engine` once to persist this chart into BEPI history.")
    else:
        weekly = history_df[["week", "geography", "bepi", "articles"]].sort_values("week")

    fig = px.line(
        weekly,
        x="week",
        y="bepi",
        color="geography",
        markers=True,
        hover_data={"articles": True, "week": True, "bepi": ":.1f"},
        labels={"week": "Week", "bepi": "BEPI score", "geography": "Geography"},
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_yaxes(range=[-100, 100])
    fig.update_xaxes(tickformat="%b %d")
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)

    export = weekly.copy()
    export["week"] = export["week"].dt.strftime("%Y-%m-%d")
    st.download_button(
        "Download Weekly BEPI CSV",
        export.to_csv(index=False).encode("utf-8"),
        file_name="weekly_bepi.csv",
        mime="text/csv",
    )

with topics_tab:
    left, right = st.columns([1, 1])
    with left:
        topic_geo = (
            all_df.groupby(["topic", "geography"], as_index=False)
            .agg(bepi=("bepi_signal", "mean"), articles=("id", "count"))
            .sort_values("bepi")
        )
        fig_topic = px.bar(
            topic_geo,
            x="bepi",
            y="topic",
            color="geography",
            barmode="group",
            hover_data={"articles": True, "bepi": ":.1f"},
            labels={"bepi": "Average BEPI", "topic": "Topic"},
        )
        fig_topic.add_vline(x=0, line_dash="dash", line_color="gray")
        fig_topic.update_layout(height=520, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_topic, use_container_width=True)

    with right:
        weekly_topic = (
            all_df.groupby(["week", "topic"], as_index=False)
            .agg(articles=("id", "count"), bepi=("bepi_signal", "mean"))
        )
        fig_volume = px.bar(
            weekly_topic,
            x="week",
            y="articles",
            color="topic",
            labels={"week": "Week", "articles": "Article count"},
        )
        fig_volume.update_xaxes(tickformat="%b %d")
        fig_volume.update_layout(height=520, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_volume, use_container_width=True)

with policy_tab:
    st.subheader("Policy Intelligence Lab")
    st.caption("Generate evidence-grounded memos from the articles already collected in your hub.")

    controls, preview = st.columns([1, 1.25])
    with controls:
        brief_type = st.selectbox(
            "Output type",
            ["Decision memo", "Evidence pack", "Bangladesh relevance note", "Research question map"],
        )
        audience = st.selectbox(
            "Audience",
            ["Bangladesh policy analyst", "Economics student", "Central bank watcher", "Development researcher", "Public explainer"],
        )
        geo_filter = st.selectbox("Geography filter", ["all", "bangladesh", "global"], index=1)
        topic_options = ["all"] + sorted(all_df["topic"].dropna().unique().tolist())
        topic_filter = st.selectbox("Topic filter", topic_options)
        focus_question = st.text_input(
            "Focus question",
            placeholder="Example: What is the current inflation pressure signal for Bangladesh?",
        )
        article_count = st.slider("Use top articles", min_value=3, max_value=min(12, len(all_df)), value=min(6, len(all_df)))

    candidate_df = all_df.copy()
    if geo_filter != "all":
        candidate_df = candidate_df[candidate_df["geography"] == geo_filter]
    if topic_filter != "all":
        candidate_df = candidate_df[candidate_df["topic"] == topic_filter]
    candidate_df = candidate_df.sort_values(["article_date", "bepi_signal"], ascending=[False, False]).head(article_count)

    with preview:
        st.markdown("#### Evidence Set")
        if candidate_df.empty:
            st.info("No articles match this filter yet. Try geography=all or topic=all.")
        else:
            display_cols = ["title", "source", "topic", "geography", "bepi_signal"]
            st.dataframe(candidate_df[display_cols], use_container_width=True, hide_index=True)

    if "latest_policy_brief" not in st.session_state:
        st.session_state.latest_policy_brief = ""
        st.session_state.latest_policy_title = ""

    can_generate = not candidate_df.empty
    if st.button("Generate Brief", type="primary", disabled=not can_generate):
        records = candidate_df.to_dict(orient="records")
        with st.spinner("Generating your brief from the evidence set..."):
            content = generate_brief(
                records,
                brief_type=brief_type,
                focus_question=focus_question,
                audience=audience,
                geography=geo_filter,
                topic=topic_filter,
            )
        title = focus_question.strip() or f"{brief_type}: {geo_filter} {topic_filter}"
        article_ids = [int(row["id"]) for row in records]
        if using_sample_data:
            brief_id = None
        else:
            brief_id = save_brief(title, brief_type, focus_question, geo_filter, topic_filter, article_ids, content)
        st.session_state.latest_policy_brief = content
        st.session_state.latest_policy_title = f"brief_{brief_id}.md" if brief_id else "sample_brief.md"
        if brief_id:
            st.success(f"Saved brief #{brief_id}")
        else:
            st.success("Generated sample brief. Connect a live database to save briefs.")

    if st.session_state.latest_policy_brief:
        st.markdown("#### Generated Brief")
        st.markdown(st.session_state.latest_policy_brief)
        st.download_button(
            "Download Markdown Brief",
            st.session_state.latest_policy_brief.encode("utf-8"),
            file_name=st.session_state.latest_policy_title or "policy_brief.md",
            mime="text/markdown",
        )

    recent = [] if using_sample_data else list_recent_briefs(limit=5)
    if recent:
        st.markdown("#### Recent Saved Briefs")
        for brief in recent:
            with st.expander(f"{brief['created_at']} | {brief['title']} | {brief['brief_type']}"):
                st.markdown(brief["content"])

with articles_tab:
    query = st.text_input("Search articles", placeholder="inflation, Bangladesh exports, monetary policy...")
    geo = st.selectbox("Geography", ["all", "bangladesh", "global"])
    topic_options = ["all"] + sorted(all_df["topic"].dropna().unique().tolist())
    topic = st.selectbox("Topic", topic_options)

    filtered = all_df.copy()
    if geo != "all":
        filtered = filtered[filtered["geography"] == geo]
    if topic != "all":
        filtered = filtered[filtered["topic"] == topic]
    if query:
        q = query.lower()
        filtered = filtered[
            filtered["title"].fillna("").str.lower().str.contains(q)
            | filtered["summary"].fillna("").str.lower().str.contains(q)
        ]

    if filtered.empty:
        st.info("No matching articles yet.")
    for _, row in filtered.head(100).iterrows():
        st.markdown(f"### [{row['title']}]({row['url']})")
        st.caption(
            f"{row['source']} | {row['geography']} | {row['topic']} | BEPI: {row['bepi_signal']:.1f}"
        )
        if row["summary"]:
            st.write(row["summary"])
        st.divider()

if conn is not None:
    conn.close()

