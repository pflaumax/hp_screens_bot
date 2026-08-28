#!/usr/bin/env python3
"""Print sample captions without touching Bluesky.

Renders exactly what would be posted — fact, blank line, film title,
hashtag — so the fact wording can be judged before it goes live.
Needs no screenshots on disk; movie titles come from movie_metadata.json.

Usage:
    python scripts/preview_facts.py [count]
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.caption_generator import BLUESKY_CHAR_LIMIT, fact_budget, generate
from bot.fact_fetcher import FactFetcher
from bot.movie_library import Movie


def _load_movies(metadata_path: Path) -> list[Movie]:
    """Read movie_metadata.json without scanning any screenshot folders."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    return [Movie(**entry) for entry in metadata["movies"]]


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    movies = _load_movies(Path("data/movie_metadata.json"))
    fetcher = FactFetcher(Path("data/cache"))
    seen: set[str] = set()

    for i in range(1, count + 1):
        movie = random.choice(movies)
        fact = fetcher.get_random_fact(
            exclude_ids=seen, max_length=fact_budget(movie, 180)
        )
        if fact:
            seen.add(fact.fact_id)

        caption, hashtags = generate(movie, fact.text if fact else None)
        full = f"{caption}\n" + " ".join(f"#{t}" for t in hashtags)
        label = fact.content_type if fact else "no fact"

        print(f"--- {i} [{label}] {len(full)}/{BLUESKY_CHAR_LIMIT} chars ---")
        print(full)
        print()


if __name__ == "__main__":
    main()
