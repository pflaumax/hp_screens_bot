"""Tests for bot.caption_generator."""

import re

import pytest

from bot.caption_generator import generate
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

    def test_format_contains_title_and_year(
        self, sample_movie: Movie
    ) -> None:
        """Caption should contain the movie title and year."""
        caption, hashtags = generate(sample_movie)
        assert sample_movie.title in caption
        assert str(sample_movie.year) in caption

    def test_hashtags_present(self, sample_movie: Movie) -> None:
        """Caption must always include HarryPotter and movie hashtag."""
        caption, hashtags = generate(sample_movie)
        assert "HarryPotter" in hashtags
        assert sample_movie.hashtag.lstrip("#") in hashtags
        assert "WizardingWorld" in hashtags

    @pytest.mark.parametrize("movie", ALL_MOVIES, ids=lambda m: m.short_title)
    def test_caption_has_no_timestamp_line(self, movie: Movie) -> None:
        """Ensure no HH:MM:SS pattern in caption after refactor."""
        caption, hashtags = generate(movie)
        assert not re.search(r"\d{2}:\d{2}:\d{2}", caption)
