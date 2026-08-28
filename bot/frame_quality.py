"""Judge whether a screengrab is worth posting.

movie-screencaps.com samples films at a fixed interval, so every folder
carries fades to black, motion-blurred pans, corrupt files, and close-ups
of texture — a frame is captured whether or not anything is happening.

Two stages, in cost order:

1. **Cheap guards** (Pillow): unreadable files and near-black frames are
   never posted. About 0.3% of the library is truncated JPEG that would
   otherwise crash the post cycle, and another few percent are scene
   fades.

2. **Face detection** (OpenCV YuNet, ~16 ms per frame on a Pi): the only
   signal found that actually separates a character shot from a close-up
   of rubble. Luminance statistics do not: the films are shot dark, and
   measured against the real library a dark close-up of Harry's face and
   a close-up of a mosaic floor land in the same brightness and contrast
   bands. Roughly 65% of frames carry a detectable face, evenly spread
   across all eight films.

Faces are *preferred*, not required — see `bot.frame_selector`. A frame
with no face is still a legitimate wide shot, so it is used as a fallback
rather than banned.

OpenCV is optional: if it or the model is missing, the cheap guards still
apply and every readable frame counts as acceptable.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageStat

logger = logging.getLogger("hp_bot.frame_quality")

DEFAULT_MODEL_PATH = Path("models/face_detection_yunet_2023mar.onnx")

# Metrics come from a downscaled decode. JPEG lets the decoder scale by
# 1/2, 1/4 or 1/8 almost for free, which is what makes this affordable.
SAMPLE_WIDTH = 480

# Longest side the face detector sees. Tuned on the real library: large
# enough for background faces, small enough to stay at ~16 ms on a Pi.
DETECT_SIZE = 640

# Calibrated against 1500 sampled frames. Brightness p5 of the library is
# 9.2 and legitimate dark shots of faces measure 14-15, so 10 clears
# fades without touching real cinematography.
MIN_BRIGHTNESS = 10.0
MIN_CONTRAST = 6.0

# YuNet confidence. At 0.7, 65% of the library has a face; the level was
# chosen from the score distribution on real frames.
FACE_SCORE_THRESHOLD = 0.7


@dataclass(frozen=True)
class FrameAssessment:
    """The verdict on one candidate frame."""

    usable: bool
    faces: int
    reason: str = ""

    @property
    def has_face(self) -> bool:
        """Whether a face was detected above the confidence threshold."""
        return self.faces > 0


UNREADABLE = FrameAssessment(usable=False, faces=0, reason="unreadable")


class FrameScorer:
    """Applies the cheap guards, then looks for faces if OpenCV is present."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        face_score_threshold: float = FACE_SCORE_THRESHOLD,
    ) -> None:
        """Load the face detector, degrading to cheap guards if unavailable.

        Args:
            model_path: Path to the YuNet ONNX model.
            face_score_threshold: Minimum detector confidence.
        """
        self._detector = self._load_detector(model_path, face_score_threshold)

    @property
    def face_detection_available(self) -> bool:
        """Whether face detection is active for this run."""
        return self._detector is not None

    @staticmethod
    def _load_detector(model_path: Path, threshold: float) -> object | None:
        """Build the YuNet detector, or return None if it cannot be used."""
        try:
            import cv2
        except ImportError:
            logger.warning(
                "OpenCV not installed — posting without face filtering."
            )
            return None

        if not model_path.exists():
            logger.warning(
                "Face model missing at %s — posting without face filtering.",
                model_path,
            )
            return None

        try:
            return cv2.FaceDetectorYN.create(
                str(model_path), "", (320, 320), score_threshold=threshold
            )
        except Exception as exc:
            logger.warning("Could not load face detector: %s", exc)
            return None

    def assess(self, path: Path) -> FrameAssessment:
        """Judge one frame.

        Args:
            path: Path to the source JPEG.

        Returns:
            An assessment; ``usable`` is False for frames that must never
            be posted, whatever else is available.
        """
        basic = self._check_exposure(path)
        if not basic.usable or self._detector is None:
            return basic
        return FrameAssessment(usable=True, faces=self._count_faces(path))

    @staticmethod
    def _check_exposure(path: Path) -> FrameAssessment:
        """Reject unreadable files and frames with nothing in them."""
        try:
            with Image.open(path) as img:
                img.draft("L", (SAMPLE_WIDTH, SAMPLE_WIDTH))
                stat = ImageStat.Stat(img.convert("L"))
        except (OSError, ValueError) as exc:
            logger.debug("Unreadable frame %s: %s", path.name, exc)
            return UNREADABLE

        brightness, contrast = stat.mean[0], stat.stddev[0]
        if brightness < MIN_BRIGHTNESS:
            return FrameAssessment(usable=False, faces=0, reason="near-black")
        if contrast < MIN_CONTRAST:
            return FrameAssessment(usable=False, faces=0, reason="flat")
        return FrameAssessment(usable=True, faces=0)

    def _count_faces(self, path: Path) -> int:
        """Count faces above the confidence threshold, 0 on any failure."""
        import cv2

        try:
            image = cv2.imread(str(path))
            if image is None:
                return 0
            height, width = image.shape[:2]
            scale = DETECT_SIZE / max(height, width)
            if scale < 1:
                image = cv2.resize(
                    image, (round(width * scale), round(height * scale))
                )
            self._detector.setInputSize(  # type: ignore[attr-defined]
                (image.shape[1], image.shape[0])
            )
            _, faces = self._detector.detect(image)  # type: ignore[attr-defined]
            return 0 if faces is None else len(faces)
        except Exception as exc:
            logger.debug("Face detection failed on %s: %s", path.name, exc)
            return 0
