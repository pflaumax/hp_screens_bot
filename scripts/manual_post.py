#!/usr/bin/env python3
"""Trigger one post manually for testing.

Usage:
    python scripts/manual_post.py
"""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config
from bot.bluesky_client import BlueskyClient
from bot.image_processor import ImageProcessor
from bot.movie_library import MovieLibrary
from bot.utils import setup_logging
from main import PostHistory, post_random_frame


def main() -> None:
    cfg = load_config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.log_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(cfg.log_dir, "DEBUG")

    movie_library = MovieLibrary(
        cfg.screenshots_dir, cfg.data_dir / "movie_metadata.json"
    )
    image_processor = ImageProcessor()
    post_history = PostHistory(cfg.data_dir / "posted_frames.json")

    bluesky_client = BlueskyClient(cfg.bluesky_username, cfg.bluesky_password)
    bluesky_client.login()

    print("Triggering manual post...")
    post_random_frame(
        movie_library=movie_library,
        image_processor=image_processor,
        bluesky_client=bluesky_client,
        post_history=post_history,
        temp_dir=Path("temp/"),
    )
    print("Done.")


if __name__ == "__main__":
    main()
