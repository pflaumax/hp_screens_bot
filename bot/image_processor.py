"""Resize and compress images to meet Bluesky upload constraints.

Bluesky limits: max 1000px on longest side, max 1MB file size.
Crops ultra-wide images to a better aspect ratio for feed display.
"""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger("hp_bot.image_processor")

MAX_DIMENSION = 1000
MAX_BYTES = 950_000  # 950KB — safe margin under 1MB
TARGET_ASPECT_RATIO = 1.0  # 1:1 square aspect ratio for best feed display
CROP_THRESHOLD = 1.2  # Crop if wider than 1.2:1


class ImageProcessingError(Exception):
    """Raised when an image cannot be compressed to meet constraints."""


class ImageProcessor:
    """Resizes and compresses images for Bluesky upload."""

    def prepare(self, input_path: Path, output_path: Path) -> Path:
        """Resize and compress an image to Bluesky constraints.

        For ultra-wide images (wider than 1.2:1), crops to center
        to achieve 1:1 square aspect ratio for best feed display.

        Args:
            input_path: Path to the source JPEG.
            output_path: Path to write the processed JPEG.

        Returns:
            Path to the processed image.

        Raises:
            ImageProcessingError: If the image cannot be compressed enough.
        """
        img = Image.open(input_path).convert("RGB")
        original_aspect = img.size[0] / img.size[1]

        # Crop ultra-wide images to 1:1 square (center crop)
        if original_aspect > CROP_THRESHOLD:
            # Calculate new width for square aspect ratio
            target_height = img.size[1]
            target_width = target_height  # Square = width equals height

            # Center crop
            left = (img.size[0] - target_width) // 2
            right = left + target_width
            img = img.crop((left, 0, right, target_height))

            logger.debug(
                "Cropped ultra-wide image: %dx%d (%.2f:1) → %dx%d (%.2f:1)",
                img.size[0] + (left * 2),
                target_height,
                original_aspect,
                target_width,
                target_height,
                target_width / target_height,
            )

        # Resize if longest side exceeds limit
        if max(img.size) > MAX_DIMENSION:
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

        # Progressive quality reduction until under size limit
        for quality in range(95, 10, -10):
            img.save(output_path, "JPEG", quality=quality, optimize=True)
            size = output_path.stat().st_size
            if size <= MAX_BYTES:
                logger.info(
                    "Image prepared: %dx%d, %dKB (quality=%d)",
                    img.size[0],
                    img.size[1],
                    size // 1024,
                    quality,
                )
                return output_path

        raise ImageProcessingError(
            f"Cannot compress image to under {MAX_BYTES} bytes"
        )
