"""Tests for main.PostHistory and the merged post cycle.

The post cycle is exercised with fake collaborators — no network, no
Bluesky, no Potter DB.
"""

import json
from pathlib import Path

import pytest

from bot.fact_fetcher import Fact
from bot.frame_quality import FrameAssessment
from bot.movie_library import FrameResult, MovieLibrary
from main import PostHistory, post_random_frame

FACT = Fact(
    fact_id="spells_alohomora",
    content_type="spells",
    text="Alohomora (Charm) — unlocked doors and other locked objects.",
)


@pytest.fixture
def history(tmp_path: Path) -> PostHistory:
    return PostHistory(tmp_path / "posted_frames.json")


class TestPostHistory:
    """Frame ring buffer plus the unbounded fact ledger."""

    def test_records_a_post_without_a_fact(
        self, history: PostHistory, sample_frame_result: FrameResult
    ) -> None:
        history.add(sample_frame_result, "at://post/1")
        assert history.is_posted(sample_frame_result.frame_filename)
        assert history.posted_fact_ids() == set()
        assert history.get_stats()["total_posts"] == 1

    def test_records_the_fact_id(
        self, history: PostHistory, sample_frame_result: FrameResult
    ) -> None:
        history.add(sample_frame_result, "at://post/1", FACT)
        assert history.posted_fact_ids() == {"spells_alohomora"}

    def test_fact_ids_are_not_duplicated(
        self, history: PostHistory, sample_frame_result: FrameResult
    ) -> None:
        history.add(sample_frame_result, "at://post/1", FACT)
        history.add(sample_frame_result, "at://post/2", FACT)
        raw = json.loads(history._path.read_text())
        assert raw["posted_fact_ids"] == ["spells_alohomora"]

    def test_fact_ledger_survives_the_ring_buffer_rolling_over(
        self, history: PostHistory, sample_frame_result: FrameResult
    ) -> None:
        """Frames are trimmed to 500; fact IDs must not be trimmed with them."""
        history.add(sample_frame_result, "at://post/0", FACT)
        for i in range(PostHistory.MAX_ENTRIES + 5):
            history.add(sample_frame_result, f"at://post/{i + 1}")

        raw = json.loads(history._path.read_text())
        assert len(raw["posted"]) == PostHistory.MAX_ENTRIES
        assert history.posted_fact_ids() == {"spells_alohomora"}

    def test_reads_a_legacy_file_without_the_fact_key(
        self, tmp_path: Path
    ) -> None:
        """Histories written before facts existed must still load."""
        path = tmp_path / "posted_frames.json"
        path.write_text(
            json.dumps(
                {
                    "posted": [{"movie_part": 1, "frame_filename": "a.jpg"}],
                    "stats": {"total_posts": 1, "by_part": {}, "last_post": None},
                }
            )
        )
        history = PostHistory(path)
        assert history.posted_fact_ids() == set()
        assert history.is_posted("a.jpg")


class _FakeClient:
    """Captures what would have been posted to Bluesky."""

    def __init__(self) -> None:
        self.captions: list[str] = []

    def post_with_image(
        self, text: str, hashtags: list[str], image_path: Path, alt_text: str
    ) -> str:
        self.captions.append(text)
        return f"at://post/{len(self.captions)}"


class _FakeFetcher:
    """Returns a fixed fact, recording the budget it was asked for."""

    def __init__(self, fact: Fact | None) -> None:
        self._fact = fact
        self.budgets: list[int] = []

    def get_random_fact(self, exclude_ids: set[str], max_length: int) -> Fact | None:
        self.budgets.append(max_length)
        return self._fact


class TestPostCycle:
    """post_random_frame wiring, with and without a fact source."""

    def _run(
        self,
        screenshots_dir: Path,
        metadata_path: Path,
        tmp_path: Path,
        fetcher: object | None,
        scorer: object | None = None,
        candidates: int = 2,
    ) -> tuple[_FakeClient, PostHistory]:
        from bot.image_processor import ImageProcessor

        client = _FakeClient()
        history = PostHistory(tmp_path / "posted_frames.json")
        post_random_frame(
            movie_library=MovieLibrary(screenshots_dir, metadata_path),
            image_processor=ImageProcessor(),
            bluesky_client=client,  # type: ignore[arg-type]
            post_history=history,
            temp_dir=tmp_path / "temp",
            fact_fetcher=fetcher,  # type: ignore[arg-type]
            frame_scorer=scorer,  # type: ignore[arg-type]
            frame_candidates=candidates,
        )
        return client, history

    def test_posts_title_only_without_a_fetcher(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        client, history = self._run(
            screenshots_dir, metadata_path, tmp_path, None
        )
        assert client.captions and "\n\n" not in client.captions[0]
        assert history.posted_fact_ids() == set()

    def test_posts_the_fact_above_the_title(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        client, history = self._run(
            screenshots_dir, metadata_path, tmp_path, _FakeFetcher(FACT)
        )
        assert client.captions[0].startswith(FACT.text + "\n\n")
        assert history.posted_fact_ids() == {FACT.fact_id}

    def test_a_missing_fact_still_posts_the_screengrab(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        """Potter DB being unavailable must not cost us the post."""
        client, history = self._run(
            screenshots_dir, metadata_path, tmp_path, _FakeFetcher(None)
        )
        assert len(client.captions) == 1
        assert history.get_stats()["total_posts"] == 1
        assert history.posted_fact_ids() == set()

    def test_budget_leaves_room_for_the_title_and_tag(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        fetcher = _FakeFetcher(FACT)
        self._run(screenshots_dir, metadata_path, tmp_path, fetcher)
        assert fetcher.budgets and 0 < fetcher.budgets[0] <= 180

    def test_a_junk_only_library_skips_the_cycle(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        """Nothing usable to post is a skipped cycle, not a junk post."""

        class _RejectEverything:
            def assess(self, _path: Path) -> FrameAssessment:
                return FrameAssessment(usable=False, faces=0, reason="near-black")

        client, history = self._run(
            screenshots_dir, metadata_path, tmp_path, None, _RejectEverything()
        )
        assert client.captions == []
        assert history.get_stats()["total_posts"] == 0

    def test_prefers_a_frame_with_a_face(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        """Faceless draws are passed over while the budget allows."""

        class _FaceOnThirdLook:
            def __init__(self) -> None:
                self.seen: list[str] = []

            def assess(self, path: Path) -> FrameAssessment:
                self.seen.append(path.name)
                return FrameAssessment(usable=True, faces=int(len(self.seen) == 3))

        scorer = _FaceOnThirdLook()
        client, history = self._run(
            screenshots_dir, metadata_path, tmp_path, None, scorer, candidates=3
        )
        assert len(client.captions) == 1
        assert len(scorer.seen) == 3
        assert history._data["posted"][-1]["frame_filename"] == scorer.seen[2]

    def test_temp_file_is_cleaned_up(
        self, screenshots_dir: Path, metadata_path: Path, tmp_path: Path
    ) -> None:
        self._run(screenshots_dir, metadata_path, tmp_path, _FakeFetcher(FACT))
        temp_dir = tmp_path / "temp"
        assert not list(temp_dir.glob("processed_*"))
