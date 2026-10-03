from pathlib import Path

from PIL import Image

from ml.images import resize_to_webp


def test_resizes_wide_image_and_preserves_aspect_ratio(tmp_path: Path):
    source = tmp_path / "in.jpg"
    Image.new("RGB", (1200, 1800), "red").save(source)
    dest = tmp_path / "out.webp"

    resize_to_webp(source, dest, max_width=400)

    with Image.open(dest) as out:
        assert out.width == 400
        assert out.height == 600
        assert out.format == "WEBP"


def test_does_not_upscale_a_small_image(tmp_path: Path):
    """Upscaling would inflate file size for no visible gain."""
    source = tmp_path / "in.jpg"
    Image.new("RGB", (200, 300), "blue").save(source)
    dest = tmp_path / "out.webp"

    resize_to_webp(source, dest, max_width=400)

    with Image.open(dest) as out:
        assert out.width == 200


def test_output_is_substantially_smaller(tmp_path: Path):
    source = tmp_path / "in.jpg"
    Image.new("RGB", (1200, 1800), "red").save(source, quality=95)
    dest = tmp_path / "out.webp"

    resize_to_webp(source, dest, max_width=400)

    assert dest.stat().st_size < source.stat().st_size
