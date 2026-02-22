#!/usr/bin/env python3
"""Dry-run: pick a random screenshot and process it without posting.

Usage:
    python scripts/test_extraction.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config
from bot.image_processor import ImageProcessor
from bot.movie_library import MovieLibrary
from bot.utils import setup_logging


def main() -> None:
    cfg = load_config()
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(cfg.log_dir, "DEBUG")

    library = MovieLibrary(
        cfg.screenshots_dir, cfg.data_dir / "movie_metadata.json"
    )

    lib_stats = library.get_stats()
    print(f"Total frames available: {lib_stats['total_frames']}")
    for part, count in sorted(lib_stats["by_part"].items()):
        print(f"  Part {part}: {count} frames")

    result = library.get_random_frame()
    print(f"\nSelected: {result.movie.title}")
    print(f"Frame: {result.frame_filename}")
    print(f"Path: {result.frame_path}")

    temp_dir = Path("temp/")
    temp_dir.mkdir(parents=True, exist_ok=True)
    output = temp_dir / f"test_processed_{result.frame_filename}"

    processor = ImageProcessor()
    processor.prepare(result.frame_path, output)
    size_kb = output.stat().st_size // 1024
    print(f"Processed → {output} ({size_kb}KB)")
    print("Frame saved. Not posting.")


if __name__ == "__main__":
    main()
