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

    def test_small_widescreen_cropped_not_upscaled(
        self, small_frame: Path, tmp_path: Path
    ) -> None:
        """An 800x450 frame is centre-cropped to 450x450, never upscaled."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(small_frame, output)
        img = Image.open(output)
        assert img.size == (450, 450)

    def test_compressed_under_1mb(
        self, large_frame: Path, tmp_path: Path
    ) -> None:
        """Output file must always be under 950KB."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        assert output.stat().st_size <= MAX_BYTES

    def test_widescreen_cropped_to_square(
        self, large_frame: Path, tmp_path: Path
    ) -> None:
        """A 16:9 frame is centre-cropped to 1:1 for the Bluesky feed."""
        output = tmp_path / "out.jpg"
        self.processor.prepare(large_frame, output)
        img = Image.open(output)
        assert img.size[0] == img.size[1]

    def test_near_square_left_uncropped(self, tmp_path: Path) -> None:
        """Frames under the 1.2:1 threshold keep their aspect ratio."""
        source = tmp_path / "near_square.jpg"
        Image.new("RGB", (900, 800), color=(10, 20, 30)).save(source, "JPEG")
        output = tmp_path / "out.jpg"
        self.processor.prepare(source, output)
        assert Image.open(output).size == (900, 800)
