from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "bepi_data/bepi.db"))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                feed_url TEXT NOT NULL UNIQUE,
                geography TEXT NOT NULL,
                source_type TEXT DEFAULT 'rss',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                author TEXT,
                published_at TEXT,
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                raw_excerpt TEXT,
                body_text TEXT,
                summary TEXT,
                topic TEXT,
                geography TEXT,
                sentiment_score REAL,
                bepi_signal REAL,
                content_hash TEXT,
                FOREIGN KEY(source_id) REFERENCES sources(id)
            );

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
            );

            CREATE TABLE IF NOT EXISTS bepi_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                geography TEXT NOT NULL,
                score REAL NOT NULL,
                article_count INTEGER NOT NULL,
                computed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(period_start, period_end, geography)
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS article_fts USING fts5(
                title,
                body_text,
                summary,
                content='articles',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                INSERT INTO article_fts(rowid, title, body_text, summary)
                VALUES (new.id, new.title, coalesce(new.body_text, ''), coalesce(new.summary, ''));
            END;

            CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                INSERT INTO article_fts(article_fts, rowid, title, body_text, summary)
                VALUES('delete', old.id, old.title, coalesce(old.body_text, ''), coalesce(old.summary, ''));
                INSERT INTO article_fts(rowid, title, body_text, summary)
                VALUES (new.id, new.title, coalesce(new.body_text, ''), coalesce(new.summary, ''));
            END;
            """
        )

        default_sources = [
            ("The Daily Star Business", "https://www.thedailystar.net/business/rss.xml", "bangladesh"),
            ("The Financial Express", "https://thefinancialexpress.com.bd/rss.xml", "bangladesh"),
            ("CPD Bangladesh", "https://cpd.org.bd/feed/", "bangladesh"),
            ("SANEM", "https://sanemnet.org/feed/", "bangladesh"),
            ("IMF Blog", "https://www.imf.org/en/Blogs/rss", "global"),
            ("World Bank Blogs", "https://blogs.worldbank.org/rss.xml", "global"),
            ("VoxEU", "https://cepr.org/rss/vox-rss-feed", "global"),
            ("NBER New Working Papers", "https://feeds.feedburner.com/nber/new", "global"),
            ("Marginal Revolution", "https://marginalrevolution.com/feed", "global"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO sources(name, feed_url, geography) VALUES (?, ?, ?)",
            default_sources,
        )


def main() -> None:
    init_db()
    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    main()

