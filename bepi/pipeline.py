from __future__ import annotations

from bepi.analyzer import analyze
from bepi.collector import collect
from bepi.database import init_db
from bepi.index_engine import compute_scores


def main() -> None:
    init_db()
    inserted = collect()
    analyzed = analyze()
    scored = compute_scores()
    print(
        "Daily pipeline complete: "
        f"{inserted} new articles, {analyzed} analyzed, {scored} scored."
    )


if __name__ == "__main__":
    main()
