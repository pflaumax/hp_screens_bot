#!/usr/bin/env python3
"""Measure what the frame filter would do to the screenshot library.

Samples frames at random, reports how many are unreadable, near-black, or
carry a face, and times the detector. Use this before changing any
threshold in bot/frame_quality.py — the defaults there were set from this
script's output, not from guesswork. Reads only; posts nothing.

Usage:
    python scripts/calibrate_quality.py [sample_size]
"""

import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.frame_quality import FrameScorer
from bot.movie_library import MovieLibrary
from config import load_config


def main() -> None:
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    cfg = load_config()
    library = MovieLibrary(cfg.screenshots_dir, cfg.data_dir / "movie_metadata.json")
    scorer = FrameScorer()
    print(f"Face detection: {'on' if scorer.face_detection_available else 'OFF'}\n")

    verdicts: Counter[str] = Counter()
    per_movie: defaultdict[int, list[int]] = defaultdict(lambda: [0, 0])
    timings: list[float] = []

    for _ in range(sample_size):
        frame = library.get_random_frame()
        started = time.perf_counter()
        assessment = scorer.assess(frame.frame_path)
        timings.append((time.perf_counter() - started) * 1000)

        if not assessment.usable:
            verdicts[assessment.reason] += 1
        elif assessment.has_face:
            verdicts["face"] += 1
        else:
            verdicts["no face"] += 1

        counts = per_movie[frame.movie.part]
        counts[1] += 1
        if assessment.usable and assessment.has_face:
            counts[0] += 1

    print(f"Sampled {sample_size} frames, {sum(timings) / len(timings):.0f} ms each "
          f"(max {max(timings):.0f} ms)\n")
    for reason, count in verdicts.most_common():
        print(f"  {reason:>10}: {count:5d}  ({count / sample_size:6.1%})")

    print("\nFace coverage by film:")
    for part in sorted(per_movie):
        with_face, total = per_movie[part]
        print(f"  part {part}: {with_face:4d}/{total:<4d} {with_face / total:6.1%}")

    faceless = verdicts["no face"] / max(1, verdicts["face"] + verdicts["no face"])
    print(
        f"\nWith {cfg.frame_candidates} candidates, roughly "
        f"{faceless ** cfg.frame_candidates:.1%} of posts would have no face."
    )


if __name__ == "__main__":
    main()
