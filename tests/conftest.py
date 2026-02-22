"""Pytest fixtures and sample data for bot tests."""

import json
import pytest
from pathlib import Path
from PIL import Image

from bot.movie_library import Movie, FrameResult


@pytest.fixture
def screenshots_dir(tmp_path: Path) -> Path:
    """Create fake screenshot folder structure for testing."""
    movies = [
        "philosophers_stone",
        "chamber_of_secrets",
        "prisoner_of_azkaban",
    ]
    for movie in movies:
        folder = tmp_path / movie
        folder.mkdir()
        for i in range(1, 11):
            img = Image.new("RGB", (1920, 800), color=(100 + i * 10, 80, 60))
            img.save(folder / f"frame_{i:05d}.jpg", "JPEG")
    return tmp_path


@pytest.fixture
def metadata_path(tmp_path: Path) -> Path:
    """Create a test movie_metadata.json with 3 movies."""
    metadata = {
        "movies": [
            {
                "folder_name": "philosophers_stone",
                "title": "Harry Potter and the Philosopher's Stone",
                "short_title": "Philosopher's Stone",
                "year": 2001,
                "part": 1,
                "hashtag": "#PhilosophersStone",
            },
            {
                "folder_name": "chamber_of_secrets",
                "title": "Harry Potter and the Chamber of Secrets",
                "short_title": "Chamber of Secrets",
                "year": 2002,
                "part": 2,
                "hashtag": "#ChamberOfSecrets",
            },
            {
                "folder_name": "prisoner_of_azkaban",
                "title": "Harry Potter and the Prisoner of Azkaban",
                "short_title": "Prisoner of Azkaban",
                "year": 2004,
                "part": 3,
                "hashtag": "#PrisonerOfAzkaban",
            },
        ]
    }
    path = tmp_path / "movie_metadata.json"
    path.write_text(json.dumps(metadata))
    return path


@pytest.fixture
def sample_movie() -> Movie:
    """A Movie instance for caption/unit tests."""
    return Movie(
        folder_name="philosophers_stone",
        title="Harry Potter and the Philosopher's Stone",
        short_title="Philosopher's Stone",
        year=2001,
        part=1,
        hashtag="#PhilosophersStone",
    )


@pytest.fixture
def sample_frame_result(screenshots_dir: Path) -> FrameResult:
    """A valid FrameResult pointing to a real test image."""
    movie = Movie(
        folder_name="philosophers_stone",
        title="Harry Potter and the Philosopher's Stone",
        short_title="Philosopher's Stone",
        year=2001,
        part=1,
        hashtag="#PhilosophersStone",
    )
    frame_path = screenshots_dir / "philosophers_stone" / "frame_00001.jpg"
    return FrameResult(
        frame_path=frame_path,
        frame_filename="frame_00001.jpg",
        movie=movie,
    )


@pytest.fixture
def large_frame(tmp_path: Path) -> Path:
    """Create a 4K JPEG test image for resize testing."""
    img = Image.new("RGB", (3840, 2160), color=(100, 120, 140))
    path = tmp_path / "large.jpg"
    img.save(path, "JPEG")
    return path


@pytest.fixture
def small_frame(tmp_path: Path) -> Path:
    """Create an 800px JPEG test image (already under limit)."""
    img = Image.new("RGB", (800, 450), color=(100, 120, 140))
    path = tmp_path / "small.jpg"
    img.save(path, "JPEG")
    return path
