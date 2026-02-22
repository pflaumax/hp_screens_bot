"""Application entry point with signal handling.

Orchestrates the full post cycle: pick random screenshot → compress →
post to Bluesky. Runs on a 30-minute schedule.
"""

import json
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import load_config

from bot.bluesky_client import BlueskyClient, PostingError
from bot.caption_generator import generate as generate_caption
from bot.image_processor import ImageProcessor, ImageProcessingError
from bot.movie_library import MovieLibrary, FrameResult
from bot.scheduler import BotScheduler
from bot.utils import cleanup_temp_files, setup_logging

logger = logging.getLogger("hp_bot.main")


class PostHistory:
    """Ring buffer of recently posted frames to avoid duplicates."""

    MAX_ENTRIES = 500

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data = self._load()

    def _load(self) -> dict:
        """Load history from disk, or return empty structure."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load post history: %s", exc)
        return {
            "posted": [],
            "stats": {
                "total_posts": 0,
                "by_part": {},
                "last_post": None,
                "bot_started": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _save(self) -> None:
        """Atomically write history to disk."""
        tmp_path = self._path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        tmp_path.rename(self._path)

    def add(self, frame_result: FrameResult, uri: str) -> None:
        """Record a posted frame.

        Args:
            frame_result: The posted FrameResult.
            uri: Bluesky post URI.
        """
        now = datetime.now(timezone.utc).isoformat()
        self._data["posted"].append({
            "movie_part": frame_result.movie.part,
            "frame_filename": frame_result.frame_filename,
            "posted_at": now,
            "bluesky_uri": uri,
        })
        # Trim to ring buffer size
        self._data["posted"] = self._data["posted"][-self.MAX_ENTRIES:]

        stats = self._data["stats"]
        stats["total_posts"] += 1
        part_key = str(frame_result.movie.part)
        stats["by_part"][part_key] = stats["by_part"].get(part_key, 0) + 1
        stats["last_post"] = now
        self._save()

    def is_posted(self, frame_filename: str) -> bool:
        """Check if a frame filename was already posted.

        Args:
            frame_filename: JPEG filename to check.

        Returns:
            True if the filename exists in the posted buffer.
        """
        return any(
            entry.get("frame_filename") == frame_filename
            for entry in self._data["posted"]
        )

    def get_stats(self) -> dict:
        """Return posting statistics."""
        return self._data["stats"]


MAX_DUPLICATE_RETRIES = 3


def post_random_frame(
    movie_library: MovieLibrary,
    image_processor: ImageProcessor,
    bluesky_client: BlueskyClient,
    post_history: PostHistory,
    temp_dir: Path,
) -> None:
    """Execute one full post cycle.

    Picks a random screenshot, compresses it, and posts to Bluesky.
    All errors are caught and logged — the scheduler must never crash.
    """
    processed_path: Path | None = None
    try:
        # Pick a frame, retrying if it was already posted
        frame_result: FrameResult | None = None
        for attempt in range(1, MAX_DUPLICATE_RETRIES + 1):
            candidate = movie_library.get_random_frame()
            if not post_history.is_posted(candidate.frame_filename):
                frame_result = candidate
                break
            logger.info(
                "[Part %d] Frame %s already posted, retrying (%d/%d)...",
                candidate.movie.part,
                candidate.frame_filename,
                attempt,
                MAX_DUPLICATE_RETRIES,
            )

        if frame_result is None:
            # Extremely unlikely with 6000+ frames, but use last candidate
            frame_result = candidate  # type: ignore[assignment]
            logger.warning(
                "Could not find unposted frame after %d attempts, "
                "proceeding with %s",
                MAX_DUPLICATE_RETRIES,
                frame_result.frame_filename,
            )

        movie = frame_result.movie

        # Resize and compress
        temp_dir.mkdir(parents=True, exist_ok=True)
        processed_path = temp_dir / f"processed_{frame_result.frame_filename}"
        image_processor.prepare(frame_result.frame_path, processed_path)

        # Generate caption and alt text
        caption, hashtags = generate_caption(movie)
        alt_text = f"Scene from {movie.title} ({movie.year})"

        # Post to Bluesky
        try:
            uri = bluesky_client.post_with_image(
                caption, hashtags, processed_path, alt_text
            )
        except PostingError:
            logger.warning(
                "[Part %d] Image post failed, trying text-only fallback.",
                movie.part,
            )
            try:
                uri = bluesky_client.post_text_only(caption, hashtags)
            except PostingError as exc:
                logger.error(
                    "[Part %d] Text-only fallback also failed: %s",
                    movie.part, exc,
                )
                return

        post_history.add(frame_result, uri)
        logger.info(
            "Posted: %s [%s] → %s",
            movie.title, frame_result.frame_filename, uri,
        )

    except Exception as exc:
        logger.error("Unexpected error in post cycle: %s", exc, exc_info=True)
    finally:
        if processed_path:
            cleanup_temp_files(processed_path)


def main() -> None:
    """Boot the bot: load config, scan screenshots, authenticate, start scheduler."""
    cfg = load_config()

    # Ensure directories exist
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.log_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(cfg.log_dir, cfg.log_level)

    logger.info("Harry Potter Screengrab Bot starting up...")

    # Initialise components
    movie_library = MovieLibrary(
        cfg.screenshots_dir, cfg.data_dir / "movie_metadata.json"
    )
    if not movie_library.movies:
        logger.error("No movies found in %s. Exiting.", cfg.screenshots_dir)
        sys.exit(1)

    image_processor = ImageProcessor()
    post_history = PostHistory(cfg.data_dir / "posted_frames.json")
    temp_dir = Path("temp/")

    bluesky_client = BlueskyClient(cfg.bluesky_username, cfg.bluesky_password)
    bluesky_client.login()

    # Set bot_started if not already set
    stats = post_history.get_stats()
    if stats.get("bot_started") is None:
        post_history._data["stats"]["bot_started"] = (
            datetime.now(timezone.utc).isoformat()
        )
        post_history._save()

    # Log library stats
    lib_stats = movie_library.get_stats()
    logger.info(
        "Bot started. %d movies, %d total frames. Posting every %d minutes.",
        len(movie_library.movies),
        lib_stats["total_frames"],
        cfg.interval_minutes,
    )

    # Build the post function with all dependencies bound
    def do_post() -> None:
        post_random_frame(
            movie_library=movie_library,
            image_processor=image_processor,
            bluesky_client=bluesky_client,
            post_history=post_history,
            temp_dir=temp_dir,
        )

    # Run one post immediately on startup
    do_post()

    # Start scheduler
    scheduler = BotScheduler(do_post, cfg.interval_minutes)
    scheduler.start()

    # Graceful shutdown on signals
    def handle_signal(signum: int, _frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s. Shutting down...", sig_name)
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Block main thread
    logger.info("Scheduler running. Waiting for next cycle...")
    try:
        signal.pause()
    except AttributeError:
        # signal.pause() not available on Windows
        import time
        while True:
            time.sleep(60)


if __name__ == "__main__":
    main()
