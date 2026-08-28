#!/usr/bin/env python3
"""Show posting statistics from the post history.

Film names come from data/movie_metadata.json, which is the source of
truth for the movie list — this script used to keep its own copy and
silently drift from it.

Usage:
    python scripts/stats.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config


def _film_names(metadata_path: Path) -> dict[int, str]:
    """Map part number to short title, or {} if the metadata is missing."""
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Warning: could not read {metadata_path}: {exc}", file=sys.stderr)
        return {}
    return {entry["part"]: entry["short_title"] for entry in metadata["movies"]}


def main() -> None:
    cfg = load_config()
    history_path = cfg.data_dir / "posted_frames.json"
    if not history_path.exists():
        print(f"No post history at {history_path}.")
        return

    data = json.loads(history_path.read_text(encoding="utf-8"))
    names = _film_names(cfg.data_dir / "movie_metadata.json")
    stats = data.get("stats", {})
    posted = data.get("posted", [])

    print(f"Bot started:  {stats.get('bot_started', 'unknown')}")
    print(f"Total posts:  {stats.get('total_posts', 0)}")
    print(f"Last post:    {stats.get('last_post', 'never')}")

    by_part = stats.get("by_part", {})
    if by_part:
        total = sum(by_part.values()) or 1
        print("\nPosts by film:")
        for part in sorted(by_part, key=int):
            label = names.get(int(part), f"Part {part}")
            count = by_part[part]
            print(f"  {label:<24} {count:6d}  ({count / total:5.1%})")

    fact_ids = data.get("posted_fact_ids", [])
    with_fact = sum(1 for entry in posted if entry.get("fact_id"))
    print(f"\nFacts used:   {len(fact_ids)} distinct")
    print(
        f"Recent posts: {with_fact} of the last {len(posted)} carried a fact"
        if posted
        else "Recent posts: none recorded"
    )

    if posted:
        print("\nLast 5:")
        for entry in posted[-5:]:
            label = names.get(entry.get("movie_part"), "?")
            fact = " +fact" if entry.get("fact_id") else ""
            print(
                f"  {entry.get('posted_at', '?')}  {label:<24} "
                f"{entry.get('frame_filename', 'unknown')}{fact}"
            )


if __name__ == "__main__":
    main()
