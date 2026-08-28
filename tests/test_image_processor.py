"""Tests for bot.image_processor (crop, resize, compress)."""

from pathlib import Path

import pytest
from PIL import Image

from bot.image_processor import (
    MAX_BYTES,
    MAX_DIMENSION,
    TARGET_ASPECT_RATIO,
    ImageProcessor,
)


def _make(path: Path, size: tuple[int, int]) -> Path:
    """Write a noisy JPEG, so compression behaves like a real frame."""
    noise = Image.effect_noise(size, 40).convert("RGB")
    noise.save(path, "JPEG", quality=95)
    return path


class TestImageProcessor:
    """Cropping to the target ratio and fitting Bluesky's limits."""

    processor = ImageProcessor()

    def test_cinemascope_source_keeps_full_height(self, tmp_path: Path) -> None:
        """The real library shape: 1920x800 becomes 1067x800, not 800x800."""
        source = _make(tmp_path / "scope.jpg", (1920, 800))
        output = tmp_path / "out.jpg"
        self.processor.prepare(source, output)
        assert Image.open(output).size == (1067, 800)

    def test_crops_to_the_target_ratio(self, large_frame: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        width, height = Image.open(output).size
        assert abs(width / height - TARGET_ASPECT_RATIO) < 0.01

    def test_large_image_resized(self, large_frame: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        assert max(Image.open(output).size) <= MAX_DIMENSION

    def test_compressed_under_limit(self, large_frame: Path, tmp_path: Path) -> None:
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        assert output.stat().st_size <= MAX_BYTES

    def test_small_frame_is_cropped_but_never_upscaled(
        self, small_frame: Path, tmp_path: Path
    ) -> None:
        """800x450 crops to 600x450; the height is not stretched to fill."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(small_frame, output)
        assert Image.open(output).size == (600, 450)

    def test_frame_within_tolerance_left_alone(self, tmp_path: Path) -> None:
        """A source already near the target ratio is not re-cropped."""
        source = _make(tmp_path / "near.jpg", (1360, 1000))  # 1.36:1
        output = tmp_path / "out.jpg"
        self.processor.prepare(source, output)
        assert Image.open(output).size == (1360, 1000)

    def test_taller_than_target_is_untouched(self, tmp_path: Path) -> None:
        """Portrait sources are never widened."""
        source = _make(tmp_path / "portrait.jpg", (600, 900))
        output = tmp_path / "out.jpg"
        self.processor.prepare(source, output)
        assert Image.open(output).size == (600, 900)

    @pytest.mark.parametrize("ratio", [1.0, 1.25, 1.5])
    def test_ratio_is_configurable(self, ratio: float, tmp_path: Path) -> None:
        source = _make(tmp_path / "scope.jpg", (1920, 800))
        output = tmp_path / "out.jpg"
        ImageProcessor(aspect_ratio=ratio).prepare(source, output)
        assert Image.open(output).size == (round(800 * ratio), 800)

    def test_wider_crop_yields_more_horizontal_pixels(
        self, tmp_path: Path
    ) -> None:
        """The point of the 4:3 default: sharper on a width-fitted feed."""
        source = _make(tmp_path / "scope.jpg", (1920, 800))
        square = tmp_path / "square.jpg"
        wide = tmp_path / "wide.jpg"
        ImageProcessor(aspect_ratio=1.0).prepare(source, square)
        ImageProcessor(aspect_ratio=4 / 3).prepare(source, wide)
        assert Image.open(wide).size[0] > Image.open(square).size[0]
