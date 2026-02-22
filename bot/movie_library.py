"""Screenshot folder scanner and random frame picker.

Scans pre-downloaded screenshot folders and provides random frame
selection from the cached file lists.
"""

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("hp_bot.movie_library")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class Movie:
    """Metadata for a single Harry Potter movie."""

    folder_name: str
    title: str
    short_title: str
    year: int
    part: int
    hashtag: str


@dataclass(frozen=True)
class FrameResult:
    """A randomly selected screenshot frame with its movie metadata."""

    frame_path: Path
    frame_filename: str
    movie: Movie


class MovieLibrary:
    """Scans screenshot folders and provides random frame selection."""

    def __init__(self, screenshots_dir: Path, metadata_path: Path) -> None:
        """Initialise the library.

        Args:
            screenshots_dir: Root directory containing movie subfolders.
            metadata_path: Path to movie_metadata.json.
        """
        self._screenshots_dir = screenshots_dir
        self._metadata_path = metadata_path
        self._movies: list[Movie] = []
        self._frame_pool: dict[int, list[Path]] = {}
        self._scan()

    def _scan(self) -> None:
        """Load metadata and cache frame file lists per movie."""
        with open(self._metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        for entry in metadata["movies"]:
            folder = self._screenshots_dir / entry["folder_name"]
            if not folder.is_dir():
                logger.warning(
                    "Folder missing for '%s': %s", entry["title"], folder
                )
                continue

            frames = sorted(
                p for p in folder.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            )

            if not frames:
                logger.warning(
                    "No JPEG files in folder for '%s': %s",
                    entry["title"], folder,
                )
                continue

            movie = Movie(
                folder_name=entry["folder_name"],
                title=entry["title"],
                short_title=entry["short_title"],
                year=entry["year"],
                part=entry["part"],
                hashtag=entry["hashtag"],
            )
            self._movies.append(movie)
            self._frame_pool[movie.part] = frames

            logger.info(
                "[Part %d] %s — %d frames loaded",
                movie.part, movie.short_title, len(frames),
            )

        logger.info(
            "Library scan complete. %d/%d movies available.",
            len(self._movies), len(metadata["movies"]),
        )

    @property
    def movies(self) -> list[Movie]:
        """Return the list of available movies."""
        return list(self._movies)

    def get_random_frame(self) -> FrameResult:
        """Pick a random movie and a random frame from it.

        Returns:
            A FrameResult with the chosen frame path and movie metadata.

        Raises:
            RuntimeError: If no movies are available.
        """
        if not self._movies:
            raise RuntimeError("No movies available in the library.")
        movie = random.choice(self._movies)
        frame_path = random.choice(self._frame_pool[movie.part])
        return FrameResult(
            frame_path=frame_path,
            frame_filename=frame_path.name,
            movie=movie,
        )

    def get_stats(self) -> dict:
        """Return frame counts per movie part and total.

        Returns:
            Dict with per-part counts and total frame count.
        """
        counts = {
            m.part: len(self._frame_pool.get(m.part, []))
            for m in self._movies
        }
        return {
            "by_part": counts,
            "total_frames": sum(counts.values()),
        }
