from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

import feedparser
import trafilatura

from bepi.database import get_connection, init_db


def clean_date(entry) -> str | None:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()


def extract_article_text(url: str, fallback: str = "") -> str:
    for attempt in range(3):
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
                if extracted:
                    return extracted.strip()
        except Exception as exc:
            if attempt == 2:
                print(f"Article extraction failed for {url}: {exc}")
            else:
                time.sleep(1 + attempt)
    return fallback.strip()


def parse_feed_with_retry(feed_url: str, attempts: int = 3):
    last_error = None
    for attempt in range(attempts):
        try:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
                last_error = getattr(feed, "bozo_exception", "unknown feed parse error")
                raise RuntimeError(last_error)
            return feed
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2 + attempt)
    raise RuntimeError(f"Feed failed after {attempts} attempts: {last_error}")


def collect() -> int:
    init_db()
    inserted = 0
    with get_connection() as conn:
        sources = conn.execute("SELECT id, name, feed_url, geography FROM sources").fetchall()
        for source in sources:
            print(f"Fetching {source['name']}...")
            try:
                feed = parse_feed_with_retry(source["feed_url"])
            except Exception as exc:
                print(f"Skipping {source['name']}: {exc}")
                continue
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "").strip()
                url = getattr(entry, "link", "").strip()
                if not title or not url:
                    continue

                excerpt = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                body_text = extract_article_text(url, excerpt)
                content_hash = hashlib.sha256((title + url).encode("utf-8")).hexdigest()
                author = getattr(entry, "author", None)
                published_at = clean_date(entry)

                try:
                    conn.execute(
                        """
                        INSERT INTO articles(
                            source_id, title, url, author, published_at, raw_excerpt,
                            body_text, geography, content_hash
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            source["id"], title, url, author, published_at, excerpt,
                            body_text, source["geography"], content_hash,
                        ),
                    )
                    inserted += 1
                except Exception:
                    continue
        conn.commit()
    print(f"Collected {inserted} new articles")
    return inserted


if __name__ == "__main__":
    collect()
