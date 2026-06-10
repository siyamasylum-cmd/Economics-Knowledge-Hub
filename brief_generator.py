from __future__ import annotations

from bepi.database import get_connection, init_db


def pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def main() -> None:
    init_db()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        summarized = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE summary IS NOT NULL AND trim(summary) != ''"
        ).fetchone()[0]
        topics = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE topic IS NOT NULL AND trim(topic) != ''"
        ).fetchone()[0]
        scored = conn.execute(
            "SELECT COUNT(*) FROM articles WHERE bepi_signal IS NOT NULL"
        ).fetchone()[0]
        sources = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        latest = conn.execute("SELECT MAX(collected_at) FROM articles").fetchone()[0]
        history = conn.execute("SELECT COUNT(*) FROM bepi_history").fetchone()[0]
        by_geo = conn.execute(
            """
            SELECT coalesce(geography, 'unknown') AS geography, COUNT(*) AS count
            FROM articles
            GROUP BY coalesce(geography, 'unknown')
            ORDER BY count DESC
            """
        ).fetchall()

    print("BEPI Data Quality Audit")
    print("=======================")
    print(f"Sources: {sources}")
    print(f"Articles: {total}")
    print(f"Summaries: {summarized} ({pct(summarized, total)})")
    print(f"Topics: {topics} ({pct(topics, total)})")
    print(f"BEPI signals: {scored} ({pct(scored, total)})")
    print(f"History rows: {history}")
    print(f"Latest collection: {latest or 'none'}")
    print("")
    print("Articles by geography:")
    for row in by_geo:
        print(f"- {row['geography']}: {row['count']}")


if __name__ == "__main__":
    main()
