"""Crop and compress screengrabs for the Bluesky feed.

The source library is 2.40:1 cinemascope (1920x800). Posting that
untouched gives a letterbox sliver in the feed, so frames are
centre-cropped to a taller ratio.

Which ratio is a resolution decision, not just a taste one. Feeds fit an
image to the column width, so the crop's *width in pixels* is what sets
how sharp it looks — and the source height caps it at 800. A 1:1 crop is
only 800px wide and a phone has to stretch it about 1.46x; the 4:3
default is 1067px and stretches 1.10x, while keeping more of the frame.
Squarer therefore means softer, which is the opposite of the intuition.

Compression is not the constraint. Re-encoding at quality 95 costs an
RMSE of ~0.35 on a 0-255 scale — imperceptible — and lands around 100KB
against Bluesky's ~1MB blob limit, so the quality ladder below almost
never has to step down.
"""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger("hp_bot.image_processor")

# Bluesky renders up to 2000px on the long side; there is no reason to
# throw away pixels below that.
MAX_DIMENSION = 2000

MAX_BYTES = 950_000  # safe margin under the 1MB blob limit

# Target width:height for the centre crop.
TARGET_ASPECT_RATIO = 4 / 3

# Only crop frames meaningfully wider than the target, so a source that
# is already close to it is left alone.
CROP_TOLERANCE = 1.05

# 4:4:4 chroma. The byte budget is nowhere near spent, so there is no
# reason to throw away colour resolution.
JPEG_SUBSAMPLING = 0

QUALITY_LADDER = range(95, 10, -10)


class ImageProcessingError(Exception):
    """Raised when an image cannot be compressed to meet constraints."""


class ImageProcessor:
    """Crops and compresses images for Bluesky upload."""

    def __init__(self, aspect_ratio: float = TARGET_ASPECT_RATIO) -> None:
        """Initialise the processor.

        Args:
            aspect_ratio: Target width:height for the centre crop.
        """
        self._aspect_ratio = aspect_ratio

    def prepare(self, input_path: Path, output_path: Path) -> Path:
        """Crop and compress an image to Bluesky constraints.

        Args:
            input_path: Path to the source JPEG.
            output_path: Path to write the processed JPEG.

        Returns:
            Path to the processed image.

        Raises:
            ImageProcessingError: If the image cannot be compressed enough.
        """
        img = Image.open(input_path).convert("RGB")
        img = self._crop(img)

        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

        for quality in QUALITY_LADDER:
            img.save(
                output_path,
                "JPEG",
                quality=quality,
                optimize=True,
                subsampling=JPEG_SUBSAMPLING,
            )
            size = output_path.stat().st_size
            if size <= MAX_BYTES:
                logger.info(
                    "Image prepared: %dx%d, %dKB (quality=%d)",
                    img.size[0], img.size[1], size // 1024, quality,
                )
                return output_path

        raise ImageProcessingError(
            f"Cannot compress image to under {MAX_BYTES} bytes"
        )

    def _crop(self, img: Image.Image) -> Image.Image:
        """Centre-crop to the target ratio, never widening or upscaling."""
        width, height = img.size
        if width / height <= self._aspect_ratio * CROP_TOLERANCE:
            return img

        target_width = min(width, round(height * self._aspect_ratio))
        left = (width - target_width) // 2
        cropped = img.crop((left, 0, left + target_width, height))
        logger.debug(
            "Cropped %dx%d (%.2f:1) to %dx%d (%.2f:1)",
            width, height, width / height,
            cropped.size[0], cropped.size[1],
            cropped.size[0] / cropped.size[1],
        )
        return cropped
