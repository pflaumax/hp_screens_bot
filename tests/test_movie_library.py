"""Tests for bot.movie_library (screenshot folder scanner)."""

import json
from collections import Counter
from pathlib import Path

from bot.movie_library import MovieLibrary, FrameResult


class TestMovieLibrary:
    """Screenshot folder scanning and random frame selection tests."""

    def test_scans_all_folders(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """MovieLibrary finds all 3 test movie folders."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        assert len(lib.movies) == 3

    def test_returns_frame_result_type(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """get_random_frame() returns a FrameResult dataclass."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        result = lib.get_random_frame()
        assert isinstance(result, FrameResult)

    def test_frame_path_exists(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """Returned frame_path is a real file that exists."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        result = lib.get_random_frame()
        assert result.frame_path.exists()
        assert result.frame_path.is_file()

    def test_missing_folder_logs_warning_not_crash(
        self, tmp_path: Path
    ) -> None:
        """MovieLibrary starts fine even if some folders are missing."""
        metadata = {
            "movies": [
                {
                    "folder_name": "nonexistent_movie",
                    "title": "Missing",
                    "short_title": "M",
                    "year": 2000,
                    "part": 99,
                    "hashtag": "#M",
                },
            ]
        }
        meta_path = tmp_path / "metadata.json"
        meta_path.write_text(json.dumps(metadata))
        lib = MovieLibrary(tmp_path, meta_path)
        assert len(lib.movies) == 0

    def test_frame_distribution_across_movies(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """Over 100 calls, all available movies are represented."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        parts = Counter(
            lib.get_random_frame().movie.part for _ in range(100)
        )
        # All 3 test movies should appear at least once
        assert len(parts) == 3

    def test_get_stats_returns_correct_counts(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """get_stats() returns accurate frame counts per part."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        stats = lib.get_stats()
        assert stats["total_frames"] == 30  # 3 movies × 10 frames
        assert stats["by_part"][1] == 10
        assert stats["by_part"][2] == 10
        assert stats["by_part"][3] == 10

    def test_frame_filename_matches_path(
        self, screenshots_dir: Path, metadata_path: Path
    ) -> None:
        """frame_filename should be the basename of frame_path."""
        lib = MovieLibrary(screenshots_dir, metadata_path)
        result = lib.get_random_frame()
        assert result.frame_filename == result.frame_path.name
