"""Tests for bot.bluesky_client.

The atproto Client is replaced with a recorder — nothing reaches the
network. These pin the two things that are easy to get silently wrong:
the declared image aspect ratio, and the UTF-8 byte offsets that make the
hashtag clickable.
"""

from pathlib import Path

import pytest
from PIL import Image

from bot.bluesky_client import BlueskyClient, PostingError


class _RecordingClient:
    """Stands in for atproto.Client, capturing send_image kwargs."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_image(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("Response", (), {"uri": "at://post/1"})()

    def send_post(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("Response", (), {"uri": "at://post/text"})()


@pytest.fixture
def client() -> BlueskyClient:
    bluesky = BlueskyClient("handle.bsky.social", "app-password")
    bluesky._client = _RecordingClient()  # type: ignore[assignment]
    return bluesky


@pytest.fixture
def image(tmp_path: Path) -> Path:
    path = tmp_path / "frame.jpg"
    Image.new("RGB", (1067, 800), color=(30, 40, 50)).save(path, "JPEG")
    return path


class TestAspectRatio:
    """A missing aspect ratio makes Bluesky letterbox the post."""

    def test_declared_ratio_matches_the_uploaded_file(
        self, client: BlueskyClient, image: Path
    ) -> None:
        client.post_with_image("Caption", ["HarryPotter"], image, "alt")
        ratio = client._client.calls[0]["image_aspect_ratio"]  # type: ignore[attr-defined]
        assert (ratio.width, ratio.height) == (1067, 800)

    def test_ratio_follows_a_different_crop(
        self, client: BlueskyClient, tmp_path: Path
    ) -> None:
        path = tmp_path / "square.jpg"
        Image.new("RGB", (800, 800), color=(10, 10, 10)).save(path, "JPEG")
        client.post_with_image("Caption", ["HarryPotter"], path, "alt")
        ratio = client._client.calls[0]["image_aspect_ratio"]  # type: ignore[attr-defined]
        assert (ratio.width, ratio.height) == (800, 800)


class TestPostContent:
    """Caption assembly and clickable-hashtag offsets."""

    def test_hashtag_is_appended_to_the_caption(
        self, client: BlueskyClient, image: Path
    ) -> None:
        client.post_with_image("A fact.\n\nA Title", ["HarryPotter"], image, "alt")
        assert client._client.calls[0]["text"] == (  # type: ignore[attr-defined]
            "A fact.\n\nA Title\n#HarryPotter"
        )

    def test_facet_offsets_are_bytes_not_characters(
        self, client: BlueskyClient, image: Path
    ) -> None:
        """An em dash is 3 bytes; character offsets would land wrong."""
        caption = "Fracto Strata — destroy weak objects.\n\nA Title"
        client.post_with_image(caption, ["HarryPotter"], image, "alt")
        call = client._client.calls[0]  # type: ignore[attr-defined]
        encoded = call["text"].encode("utf-8")
        index = call["facets"][0].index
        assert encoded[index.byte_start : index.byte_end] == b"#HarryPotter"

    def test_alt_text_is_passed_through(
        self, client: BlueskyClient, image: Path
    ) -> None:
        client.post_with_image("Caption", ["HarryPotter"], image, "Scene from X")
        assert client._client.calls[0]["image_alt"] == "Scene from X"  # type: ignore[attr-defined]

    def test_text_only_fallback_keeps_the_facet(
        self, client: BlueskyClient
    ) -> None:
        client.post_text_only("Just a title", ["HarryPotter"])
        call = client._client.calls[0]  # type: ignore[attr-defined]
        encoded = call["text"].encode("utf-8")
        index = call["facets"][0].index
        assert encoded[index.byte_start : index.byte_end] == b"#HarryPotter"


class TestFailures:
    """Retries are exhausted into a PostingError, never a raw exception."""

    def test_upload_failure_raises_posting_error(
        self, client: BlueskyClient, image: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fail(**_kwargs: object) -> None:
            raise RuntimeError("upstream is down")

        monkeypatch.setattr(client._client, "send_image", _fail)
        monkeypatch.setattr("bot.utils.time.sleep", lambda _s: None)
        with pytest.raises(PostingError):
            client.post_with_image("Caption", ["HarryPotter"], image, "alt")

    def test_missing_image_file_raises_posting_error(
        self, client: BlueskyClient, tmp_path: Path
    ) -> None:
        with pytest.raises((PostingError, OSError)):
            client.post_with_image(
                "Caption", ["HarryPotter"], tmp_path / "gone.jpg", "alt"
            )
