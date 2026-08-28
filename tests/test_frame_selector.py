"""Tests for bot.frame_selector and the cheap guards in bot.frame_quality.

Face detection itself is not exercised here — it needs OpenCV and the
model — so the scorer is faked. `TestExposureGuards` covers the Pillow
half against real generated images.
"""

from pathlib import Path

import pytest
from PIL import Image

from bot.frame_quality import FrameAssessment, FrameScorer
from bot.frame_selector import select_frame
from bot.movie_library import FrameResult, Movie

MOVIE = Movie(
    folder_name="philosophers_stone",
    title="Harry Potter and the Philosopher's Stone",
    short_title="Philosopher's Stone",
    year=2001,
    part=1,
    hashtag="#PhilosophersStone",
)


class _FakeLibrary:
    """Hands out a scripted sequence of frames."""

    def __init__(self, names: list[str]) -> None:
        self._names = list(names)
        self.draws = 0

    def get_random_frame(self) -> FrameResult:
        self.draws += 1
        name = self._names[min(self.draws - 1, len(self._names) - 1)]
        return FrameResult(
            frame_path=Path(f"/frames/{name}"), frame_filename=name, movie=MOVIE
        )


class _FakeScorer:
    """Returns a verdict keyed by filename."""

    def __init__(self, verdicts: dict[str, FrameAssessment]) -> None:
        self._verdicts = verdicts
        self.assessed: list[str] = []

    def assess(self, path: Path) -> FrameAssessment:
        self.assessed.append(path.name)
        return self._verdicts[path.name]


FACE = FrameAssessment(usable=True, faces=1)
NO_FACE = FrameAssessment(usable=True, faces=0)
BROKEN = FrameAssessment(usable=False, faces=0, reason="unreadable")
DARK = FrameAssessment(usable=False, faces=0, reason="near-black")


def _never_posted(_name: str) -> bool:
    return False


class TestSelection:
    """Preferring a face without banning frames that lack one."""

    def test_takes_the_first_frame_with_a_face(self) -> None:
        library = _FakeLibrary(["a.jpg", "b.jpg", "c.jpg"])
        scorer = _FakeScorer({"a.jpg": FACE, "b.jpg": FACE, "c.jpg": FACE})
        selection = select_frame(library, _never_posted, scorer)  # type: ignore[arg-type]
        assert selection is not None
        assert selection.frame.frame_filename == "a.jpg"
        assert selection.evaluated == 1
        assert library.draws == 1  # stops as soon as it succeeds

    def test_keeps_looking_past_a_faceless_frame(self) -> None:
        library = _FakeLibrary(["a.jpg", "b.jpg", "c.jpg"])
        scorer = _FakeScorer({"a.jpg": NO_FACE, "b.jpg": NO_FACE, "c.jpg": FACE})
        selection = select_frame(
            library, _never_posted, scorer, preferred_attempts=3  # type: ignore[arg-type]
        )
        assert selection is not None
        assert selection.frame.frame_filename == "c.jpg"
        assert selection.assessment.has_face

    def test_settles_for_the_first_faceless_frame(self) -> None:
        """A wide shot is still a legitimate screengrab."""
        library = _FakeLibrary(["a.jpg", "b.jpg", "c.jpg", "d.jpg"])
        scorer = _FakeScorer(
            {"a.jpg": NO_FACE, "b.jpg": NO_FACE, "c.jpg": NO_FACE, "d.jpg": FACE}
        )
        selection = select_frame(
            library, _never_posted, scorer, preferred_attempts=3  # type: ignore[arg-type]
        )
        assert selection is not None
        assert selection.frame.frame_filename == "a.jpg"
        assert not selection.assessment.has_face

    def test_unusable_frames_never_win(self) -> None:
        library = _FakeLibrary(["a.jpg", "b.jpg", "c.jpg"])
        scorer = _FakeScorer({"a.jpg": BROKEN, "b.jpg": DARK, "c.jpg": NO_FACE})
        selection = select_frame(
            library, _never_posted, scorer, preferred_attempts=1  # type: ignore[arg-type]
        )
        assert selection is not None
        assert selection.frame.frame_filename == "c.jpg"

    def test_broken_frames_do_not_consume_the_face_budget(self) -> None:
        """Only readable candidates count toward preferred_attempts."""
        library = _FakeLibrary(["a.jpg", "b.jpg", "c.jpg"])
        scorer = _FakeScorer({"a.jpg": BROKEN, "b.jpg": BROKEN, "c.jpg": FACE})
        selection = select_frame(
            library, _never_posted, scorer, preferred_attempts=1  # type: ignore[arg-type]
        )
        assert selection is not None
        assert selection.frame.frame_filename == "c.jpg"

    def test_skips_frames_already_posted(self) -> None:
        library = _FakeLibrary(["a.jpg", "b.jpg"])
        scorer = _FakeScorer({"b.jpg": FACE})
        selection = select_frame(
            library, lambda name: name == "a.jpg", scorer  # type: ignore[arg-type]
        )
        assert selection is not None
        assert selection.frame.frame_filename == "b.jpg"
        assert "a.jpg" not in scorer.assessed  # not even measured

    def test_gives_up_when_nothing_is_usable(self) -> None:
        """Skipping a cycle beats posting a corrupt frame."""
        library = _FakeLibrary(["a.jpg"])
        scorer = _FakeScorer({"a.jpg": BROKEN})
        assert select_frame(library, _never_posted, scorer, max_attempts=4) is None  # type: ignore[arg-type]

    def test_no_scorer_accepts_the_first_unposted_frame(self) -> None:
        library = _FakeLibrary(["a.jpg"])
        selection = select_frame(library, _never_posted, None)  # type: ignore[arg-type]
        assert selection is not None
        assert selection.frame.frame_filename == "a.jpg"

    def test_max_attempts_is_respected(self) -> None:
        library = _FakeLibrary(["a.jpg"])
        scorer = _FakeScorer({"a.jpg": BROKEN})
        select_frame(library, _never_posted, scorer, max_attempts=6)  # type: ignore[arg-type]
        assert library.draws == 6


class TestExposureGuards:
    """The Pillow half, against real images."""

    @pytest.fixture
    def scorer(self) -> FrameScorer:
        # A missing model disables face detection, leaving the guards.
        return FrameScorer(model_path=Path("/nonexistent/model.onnx"))

    def test_near_black_frame_is_rejected(
        self, scorer: FrameScorer, tmp_path: Path
    ) -> None:
        path = tmp_path / "fade.jpg"
        Image.new("RGB", (640, 360), color=(2, 2, 3)).save(path, "JPEG")
        assessment = scorer.assess(path)
        assert not assessment.usable
        assert assessment.reason == "near-black"

    def test_flat_frame_is_rejected(
        self, scorer: FrameScorer, tmp_path: Path
    ) -> None:
        path = tmp_path / "flat.jpg"
        Image.new("RGB", (640, 360), color=(90, 90, 90)).save(path, "JPEG")
        assessment = scorer.assess(path)
        assert not assessment.usable
        assert assessment.reason == "flat"

    def test_unreadable_file_is_rejected(
        self, scorer: FrameScorer, tmp_path: Path
    ) -> None:
        path = tmp_path / "truncated.jpg"
        path.write_bytes(b"\xff\xd8\xff\xe0 not really a jpeg")
        assessment = scorer.assess(path)
        assert not assessment.usable
        assert assessment.reason == "unreadable"

    def test_missing_file_is_rejected(
        self, scorer: FrameScorer, tmp_path: Path
    ) -> None:
        assert not scorer.assess(tmp_path / "gone.jpg").usable

    def test_normal_frame_passes(
        self, scorer: FrameScorer, screenshots_dir: Path
    ) -> None:
        """Fixture frames are flat colour, so use a real varied image."""
        path = screenshots_dir / "philosophers_stone" / "frame_00001.jpg"
        noisy = Image.effect_noise((640, 360), 60).convert("RGB")
        noisy.save(path, "JPEG")
        assert scorer.assess(path).usable

    def test_missing_model_disables_face_detection(
        self, scorer: FrameScorer
    ) -> None:
        assert not scorer.face_detection_available
