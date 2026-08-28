"""Caption assembly for screengrab posts.

A caption is an optional Potter DB fact, a blank line, then the film
title. The single #HarryPotter tag is appended by
:mod:`bot.bluesky_client`, which also builds the byte offsets that make
it clickable — so the tag must not be baked in here.

    Age Line (Charm) — prevented people above or below a certain age
    from access to a target.

    Harry Potter and the Deathly Hallows - Part 2
    #HarryPotter
"""

from bot.movie_library import Movie

BLUESKY_CHAR_LIMIT = 300
HASHTAGS = ["HarryPotter"]

# Separator between the fact and the title, and the suffix
# bluesky_client appends after the caption.
_FACT_SEPARATOR = "\n\n"
_TAG_SUFFIX = "\n" + " ".join(f"#{tag}" for tag in HASHTAGS)


def fact_budget(movie: Movie, max_fact_length: int) -> int:
    """Characters available for a fact above this movie's title.

    Args:
        movie: The movie whose title will close the caption.
        max_fact_length: Configured upper bound, applied on top of the
            hard Bluesky limit to keep facts short.

    Returns:
        Maximum fact length in characters; may be <= 0 if there is no room.
    """
    overhead = len(_FACT_SEPARATOR) + len(movie.title) + len(_TAG_SUFFIX)
    return min(max_fact_length, BLUESKY_CHAR_LIMIT - overhead)


def generate(movie: Movie, fact_text: str | None = None) -> tuple[str, list[str]]:
    """Build the caption and hashtag list for a screengrab post.

    Args:
        movie: The Movie the frame was selected from.
        fact_text: Optional formatted fact to place above the title.

    Returns:
        Tuple of (caption_text, list_of_hashtags).
    """
    if fact_text:
        caption = f"{fact_text}{_FACT_SEPARATOR}{movie.title}"
    else:
        caption = movie.title
    return caption, list(HASHTAGS)
