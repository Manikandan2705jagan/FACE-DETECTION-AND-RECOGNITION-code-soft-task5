"""EXIF-stripping tests."""
from __future__ import annotations

import io

from PIL import Image

from app.services.exif import strip_exif


def _jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (128, 128), (120, 60, 30))
    exif = Image.Exif()
    exif[271] = "JARVAS-Camera"  # Make
    exif[34853] = {1: "N"}       # GPSInfo-ish
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def test_exif_is_removed():
    original = _jpeg_with_exif()
    with Image.open(io.BytesIO(original)) as src:
        assert src.getexif()  # has metadata to begin with

    info = strip_exif(original, "image/jpeg")
    with Image.open(io.BytesIO(info.data)) as cleaned:
        assert not cleaned.getexif()
    assert info.sha256
    assert info.width == 128 and info.height == 128
