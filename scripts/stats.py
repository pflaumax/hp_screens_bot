#!/usr/bin/env python3
"""Show posting statistics from the post history.

Usage:
    python scripts/stats.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HISTORY_PATH = Path("data/posted_frames.json")

MOVIE_NAMES = {
    "1": "Philosopher's Stone",
    "2": "Chamber of Secrets",
    "3": "Prisoner of Azkaban",
    "4": "Goblet of Fire",
    "5": "Order of the Phoenix",
    "6": "Half-Blood Prince",
    "7": "Deathly Hallows Pt. 1",
    "8": "Deathly Hallows Pt. 2",
}


def main() -> None:
    if not HISTORY_PATH.exists():
        print("No post history found.")
        return

    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = data.get("stats", {})
    total = stats.get("total_posts", 0)
    last = stats.get("last_post", "never")
    started = stats.get("bot_started", "unknown")

    print(f"Bot started:  {started}")
    print(f"Total posts:  {total}")
    print(f"Last post:    {last}")
    print()
    print("Posts by movie:")
    by_part = stats.get("by_part", {})
    for part in sorted(by_part.keys(), key=int):
        name = MOVIE_NAMES.get(part, f"Part {part}")
        print(f"  {name}: {by_part[part]}")

    posted = data.get("posted", [])
    if posted:
        print(f"\nRecent posts (last 5):")
        for entry in posted[-5:]:
            name = MOVIE_NAMES.get(str(entry["movie_part"]), "?")
            filename = entry.get("frame_filename", "unknown")
            print(f"  {name} [{filename}] — {entry['posted_at']}")


if __name__ == "__main__":
    main()
