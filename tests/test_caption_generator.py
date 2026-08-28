"""Tests for bot.caption_generator."""

import re

import pytest

from bot.caption_generator import BLUESKY_CHAR_LIMIT, fact_budget, generate
from bot.movie_library import Movie

ALL_MOVIES = [
    Movie(folder_name="philosophers_stone",
          title="Harry Potter and the Philosopher's Stone",
          short_title="Philosopher's Stone", year=2001, part=1,
          hashtag="#PhilosophersStone"),
    Movie(folder_name="chamber_of_secrets",
          title="Harry Potter and the Chamber of Secrets",
          short_title="Chamber of Secrets", year=2002, part=2,
          hashtag="#ChamberOfSecrets"),
    Movie(folder_name="prisoner_of_azkaban",
          title="Harry Potter and the Prisoner of Azkaban",
          short_title="Prisoner of Azkaban", year=2004, part=3,
          hashtag="#PrisonerOfAzkaban"),
    Movie(folder_name="goblet_of_fire",
          title="Harry Potter and the Goblet of Fire",
          short_title="Goblet of Fire", year=2005, part=4,
          hashtag="#GobletOfFire"),
    Movie(folder_name="order_of_the_phoenix",
          title="Harry Potter and the Order of the Phoenix",
          short_title="Order of the Phoenix", year=2007, part=5,
          hashtag="#OrderOfThePhoenix"),
    Movie(folder_name="half_blood_prince",
          title="Harry Potter and the Half-Blood Prince",
          short_title="Half-Blood Prince", year=2009, part=6,
          hashtag="#HalfBloodPrince"),
    Movie(folder_name="deathly_hallows_part1",
          title="Harry Potter and the Deathly Hallows \u2013 Part 1",
          short_title="Deathly Hallows Pt. 1", year=2010, part=7,
          hashtag="#DeathlyHallows"),
    Movie(folder_name="deathly_hallows_part2",
          title="Harry Potter and the Deathly Hallows \u2013 Part 2",
          short_title="Deathly Hallows Pt. 2", year=2011, part=8,
          hashtag="#DeathlyHallows"),
]


class TestCaptionGenerator:
    """Caption formatting and character limit tests."""

    @pytest.mark.parametrize("movie", ALL_MOVIES, ids=lambda m: m.short_title)
    def test_all_8_movies_under_300_chars(self, movie: Movie) -> None:
        """Every movie caption must fit within Bluesky's 300-char limit."""
        caption, hashtags = generate(movie)
        full_text = caption + "\n\n" + " ".join(f"#{tag}" for tag in hashtags)
        assert len(full_text) <= 300

    def test_title_only_without_a_fact(self, sample_movie: Movie) -> None:
        """With no fact, the caption is exactly the movie title."""
        caption, _ = generate(sample_movie)
        assert caption == sample_movie.title

    def test_fact_sits_above_the_title(self, sample_movie: Movie) -> None:
        """A fact is placed above the title, separated by a blank line."""
        caption, _ = generate(sample_movie, "Alohomora unlocked doors.")
        assert caption == (
            f"Alohomora unlocked doors.\n\n{sample_movie.title}"
        )

    def test_single_hashtag(self, sample_movie: Movie) -> None:
        """Exactly one tag — the extra per-movie tags were dropped."""
        _, hashtags = generate(sample_movie, "Alohomora unlocked doors.")
        assert hashtags == ["HarryPotter"]

    @pytest.mark.parametrize("movie", ALL_MOVIES, ids=lambda m: m.short_title)
    def test_caption_has_no_timestamp_line(self, movie: Movie) -> None:
        """Ensure no HH:MM:SS pattern in caption after refactor."""
        caption, hashtags = generate(movie)
        assert not re.search(r"\d{2}:\d{2}:\d{2}", caption)

    @pytest.mark.parametrize("movie", ALL_MOVIES, ids=lambda m: m.short_title)
    def test_budget_fact_always_fits_the_limit(self, movie: Movie) -> None:
        """A fact filling the whole budget still leaves the post under 300."""
        budget = fact_budget(movie, max_fact_length=1000)
        assert budget > 0
        caption, hashtags = generate(movie, "x" * budget)
        full_text = caption + "\n" + " ".join(f"#{tag}" for tag in hashtags)
        assert len(full_text) == BLUESKY_CHAR_LIMIT

    @pytest.mark.parametrize("movie", ALL_MOVIES, ids=lambda m: m.short_title)
    def test_budget_respects_the_configured_cap(self, movie: Movie) -> None:
        """The short-fact cap wins when it is tighter than the hard limit."""
        assert fact_budget(movie, max_fact_length=80) == 80
