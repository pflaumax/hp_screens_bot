"""Minimal caption and hashtag formatter for Bluesky posts.

Generates a short, clean caption with movie title, year, and relevant
hashtags. Always well under the 300-character limit.
"""

from bot.movie_library import Movie


def generate(movie: Movie) -> tuple[str, list[str]]:
    """Generate a Bluesky caption and hashtags for a movie screengrab.

    Args:
        movie: The Movie the frame was selected from.

    Returns:
        Tuple of (caption_text, list_of_hashtags).
    """
    caption = f"{movie.title}"
    hashtags = ["HarryPotter"]
    return caption, hashtags
