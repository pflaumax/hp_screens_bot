"""Pick which screengrab to post.

Draws candidates at random and prefers one with a face in it, falling
back to the best frame seen rather than banning faceless frames outright
— a wide shot of the castle is a legitimate screengrab, just not the one
to pick first. Frames that must never be posted (unreadable files, scene
fades) are skipped whatever the budget.
"""

import logging
from dataclasses import dataclass
from typing import Callable

from bot.frame_quality import FrameAssessment, FrameScorer
from bot.movie_library import FrameResult, MovieLibrary

logger = logging.getLogger("hp_bot.frame_selector")

# Candidates to look at hoping for a face. With ~65% of the library
# carrying one, three draws leave roughly 4% of posts faceless.
PREFERRED_ATTEMPTS = 3

# Hard ceiling on draws, so a run of unreadable or already-posted frames
# cannot spin. Only unreadable/near-black/duplicate draws consume it
# without counting toward PREFERRED_ATTEMPTS.
MAX_ATTEMPTS = 15


@dataclass(frozen=True)
class Selection:
    """The chosen frame and why it was chosen."""

    frame: FrameResult
    assessment: FrameAssessment
    evaluated: int

    def describe(self) -> str:
        """One-line summary for logs."""
        detail = (
            f"{self.assessment.faces} face(s)"
            if self.assessment.has_face
            else "no face"
        )
        return f"{detail} after {self.evaluated} candidate(s)"


def select_frame(
    movie_library: MovieLibrary,
    is_posted: Callable[[str], bool],
    scorer: FrameScorer | None,
    preferred_attempts: int = PREFERRED_ATTEMPTS,
    max_attempts: int = MAX_ATTEMPTS,
) -> Selection | None:
    """Draw frames until a good one turns up.

    Args:
        movie_library: Source of random frames.
        is_posted: Predicate telling whether a filename was posted recently.
        scorer: Quality judge; None disables all filtering.
        preferred_attempts: Usable candidates to inspect before settling
            for one without a face.
        max_attempts: Hard ceiling on draws.

    Returns:
        The selection, or None if nothing usable turned up — in which
        case the caller should skip this cycle rather than post junk.
    """
    fallback: Selection | None = None
    evaluated = 0

    for _ in range(max_attempts):
        candidate = movie_library.get_random_frame()
        if is_posted(candidate.frame_filename):
            continue

        if scorer is None:
            return Selection(candidate, FrameAssessment(True, 0), evaluated + 1)

        assessment = scorer.assess(candidate.frame_path)
        if not assessment.usable:
            logger.debug(
                "Skipping %s: %s", candidate.frame_filename, assessment.reason
            )
            continue

        evaluated += 1
        if assessment.has_face:
            return Selection(candidate, assessment, evaluated)

        if fallback is None:
            fallback = Selection(candidate, assessment, evaluated)
        if evaluated >= preferred_attempts:
            break

    if fallback is not None:
        return Selection(fallback.frame, fallback.assessment, evaluated)

    logger.error("No usable frame found in %d attempts.", max_attempts)
    return None
