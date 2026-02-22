"""Tests for bot.image_processor."""

from pathlib import Path

from PIL import Image

from bot.image_processor import ImageProcessor, MAX_BYTES, MAX_DIMENSION


class TestImageProcessor:
    """Image resize and compression tests."""

    def setup_method(self) -> None:
        self.processor = ImageProcessor()

    def test_large_image_resized(
        self, large_frame: Path, tmp_path: Path
    ) -> None:
        """A 4K image should be resized so longest side <= 1000px."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        img = Image.open(output)
        assert max(img.size) <= MAX_DIMENSION

    def test_already_small_unchanged(
        self, small_frame: Path, tmp_path: Path
    ) -> None:
        """An 800px image should not be upscaled."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(small_frame, output)
        img = Image.open(output)
        assert img.size[0] == 800
        assert img.size[1] == 450

    def test_compressed_under_1mb(
        self, large_frame: Path, tmp_path: Path
    ) -> None:
        """Output file must always be under 950KB."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        assert output.stat().st_size <= MAX_BYTES

    def test_aspect_ratio_preserved(
        self, large_frame: Path, tmp_path: Path
    ) -> None:
        """Aspect ratio should be maintained after resize."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        img = Image.open(output)
        # 3840x2160 = 16:9 → resized should still be ~16:9
        ratio = img.size[0] / img.size[1]
        assert abs(ratio - (16 / 9)) < 0.05
