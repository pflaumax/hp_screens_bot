"""Bluesky AT Protocol client wrapper with retry logic.

Handles authentication, image upload, and posting to Bluesky
with exponential backoff on transient failures.
"""

import logging
from pathlib import Path

from atproto import Client, models

from bot.utils import retry_with_backoff

logger = logging.getLogger("hp_bot.bluesky_client")


class PostingError(Exception):
    """Raised when posting to Bluesky fails after all retries."""


class BlueskyClient:
    """Wrapper around the atproto Client for posting screengrabs."""

    def __init__(self, username: str, password: str) -> None:
        """Initialise the client.

        Args:
            username: Bluesky handle (e.g. "hpscreengrab.bsky.social").
            password: App password from Bluesky settings.
        """
        self._username = username
        self._password = password
        self._client = Client()

    def login(self) -> None:
        """Authenticate with Bluesky. Call once on startup.

        Raises:
            PostingError: If authentication fails.
        """
        try:
            self._client.login(self._username, self._password)
            logger.info("Logged in to Bluesky as %s", self._username)
        except Exception as exc:
            raise PostingError(f"Bluesky login failed: {exc}") from exc

    def _build_facets(self, text: str, hashtags: list[str]) -> list:
        """Build facets for clickable hashtags.

        Args:
            text: The main text before hashtags.
            hashtags: List of hashtag strings (without # prefix).

        Returns:
            List of facet objects for the atproto client.
        """
        facets = []
        hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
        full_text = f"{text}\n{hashtag_text}"
        current_pos = len(text) + 1  # After text + 1 newline

        for tag in hashtags:
            tag_with_hash = f"#{tag}"
            byte_start = len(full_text[:current_pos].encode("utf-8"))
            byte_end = byte_start + len(tag_with_hash.encode("utf-8"))

            facets.append(
                models.AppBskyRichtextFacet.Main(
                    index=models.AppBskyRichtextFacet.ByteSlice(
                        byte_start=byte_start,
                        byte_end=byte_end,
                    ),
                    features=[models.AppBskyRichtextFacet.Tag(tag=tag)],
                )
            )
            current_pos += len(tag_with_hash) + 1  # +1 for space

        return facets

    def post_with_image(
        self,
        text: str,
        hashtags: list[str],
        image_path: Path,
        alt_text: str,
    ) -> str:
        """Post an image with caption and clickable hashtags to Bluesky.

        Args:
            text: Post caption text (without hashtags).
            hashtags: List of hashtag strings (without # prefix).
            image_path: Path to the JPEG image.
            alt_text: Accessibility alt text for the image.

        Returns:
            Bluesky post URI on success.

        Raises:
            PostingError: If all retries are exhausted.
        """
        def _do_post() -> str:
            # Build full text with hashtags
            hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
            full_text = f"{text}\n{hashtag_text}"

            # Create facets for clickable hashtags
            facets = self._build_facets(text, hashtags)

            # Upload image
            with open(image_path, "rb") as f:
                image_data = f.read()

            response = self._client.send_image(
                text=full_text,
                image=image_data,
                image_alt=alt_text,
                facets=facets,
            )
            return response.uri

        try:
            uri = retry_with_backoff(_do_post, max_retries=3, base_delay=2.0)
            logger.info("Posted successfully → %s", uri)
            return uri
        except Exception as exc:
            raise PostingError(
                f"Failed to post image after retries: {exc}"
            ) from exc

    def post_text_only(self, text: str, hashtags: list[str]) -> str:
        """Fallback: post caption without an image.

        Args:
            text: Post caption text (without hashtags).
            hashtags: List of hashtag strings (without # prefix).

        Returns:
            Bluesky post URI on success.

        Raises:
            PostingError: If all retries are exhausted.
        """
        def _do_post() -> str:
            # Build full text with hashtags
            hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
            full_text = f"{text}\n{hashtag_text}"

            # Create facets for clickable hashtags
            facets = self._build_facets(text, hashtags)

            response = self._client.send_post(text=full_text, facets=facets)
            return response.uri

        try:
            uri = retry_with_backoff(_do_post, max_retries=3, base_delay=2.0)
            logger.info("Posted text-only → %s", uri)
            return uri
        except Exception as exc:
            raise PostingError(
                f"Failed to post text after retries: {exc}"
            ) from exc
