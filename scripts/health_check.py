#!/usr/bin/env python3
"""Pre-flight check: everything the bot needs before it posts.

Verifies credentials, the screenshot library, the face model, Potter DB
reachability, and that the runtime directories are writable. Posts
nothing. Exits non-zero if any check fails, so it is usable from a
deploy script.

Usage:
    python scripts/health_check.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.fact_fetcher import FactFetcher
from bot.frame_quality import FrameScorer
from bot.movie_library import MovieLibrary
from config import load_config


def _report(label: str, ok: bool, detail: str) -> bool:
    """Print one result line and pass the verdict back through."""
    print(f"  {'OK  ' if ok else 'FAIL'}  {label:<22} {detail}")
    return ok


def check_screenshots(cfg) -> bool:
    """The screenshot library scans and has frames in every folder."""
    try:
        library = MovieLibrary(
            cfg.screenshots_dir, cfg.data_dir / "movie_metadata.json"
        )
    except OSError as exc:
        return _report("screenshots", False, str(exc))

    stats = library.get_stats()
    movies = len(library.movies)
    return _report(
        "screenshots",
        movies == 8,
        f"{movies}/8 films, {stats['total_frames']:,} frames "
        f"in {cfg.screenshots_dir}",
    )


def check_face_model(cfg) -> bool:
    """OpenCV and the YuNet model are both present."""
    if not cfg.frame_quality_enabled:
        return _report("face detection", True, "disabled by config")
    scorer = FrameScorer()
    return _report(
        "face detection",
        scorer.face_detection_available,
        "ready" if scorer.face_detection_available
        else "unavailable — install opencv-python-headless, check models/",
    )


def check_facts(cfg) -> bool:
    """Potter DB answers, or a cache is on disk to fall back to."""
    if not cfg.facts_enabled:
        return _report("facts", True, "disabled by config")

    fetcher = FactFetcher(cfg.data_dir / "cache")
    fact = fetcher.get_random_fact(exclude_ids=set(), max_length=180)
    if fact is None:
        return _report("facts", False, "no fact could be produced")
    return _report("facts", True, f"{fact.content_type}: {fact.text[:48]}…")


def check_writable(cfg) -> bool:
    """Runtime directories accept writes."""
    for label, directory in (
        ("data", cfg.data_dir),
        ("logs", cfg.log_dir),
        ("temp", Path("temp/")),
    ):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return _report("writable dirs", False, f"{label}: {exc}")
    return _report("writable dirs", True, "data, logs, temp")


def check_bluesky(cfg) -> bool:
    """Credentials are accepted. This is the only network call to Bluesky."""
    from bot.bluesky_client import BlueskyClient, PostingError

    try:
        BlueskyClient(cfg.bluesky_username, cfg.bluesky_password).login()
    except PostingError as exc:
        return _report("bluesky", False, str(exc))
    return _report("bluesky", True, f"logged in as {cfg.bluesky_username}")


def main() -> None:
    cfg = load_config()  # exits if credentials are missing
    print("Harry Potter Screengrab Bot — health check\n")

    results = [
        check_screenshots(cfg),
        check_face_model(cfg),
        check_facts(cfg),
        check_writable(cfg),
        check_bluesky(cfg),
    ]

    failed = results.count(False)
    print()
    if failed:
        print(f"{failed} check(s) failed.")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
