"""EXIF stripping and basic image normalisation.

Uploaded images are re-encoded without metadata so GPS, device, timestamps and
other identifying EXIF tags never reach storage.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageOps

# Pillow guards against decompression bombs; keep a sane ceiling.
Image.MAX_IMAGE_PIXELS = 64_000_000

_FORMAT_BY_MIME = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


@dataclass
class ImageInfo:
    data: bytes
    width: int
    height: int
    sha256: str
    format: str
    had_exif: bool


def strip_exif(data: bytes, content_type: str = "image/jpeg") -> ImageInfo:
    """Re-encode ``data`` without EXIF/ICC metadata and return clean bytes."""
    fmt = _FORMAT_BY_MIME.get(content_type, "JPEG")
    with Image.open(io.BytesIO(data)) as img:
        had_exif = bool(img.getexif())
        # Apply orientation before dropping metadata so the image looks right.
        img = ImageOps.exif_transpose(img)
        if fmt == "JPEG" and img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif fmt in ("PNG", "WEBP") and img.mode == "P":
            img = img.convert("RGBA") if fmt == "PNG" else img.convert("RGB")

        buffer = io.BytesIO()
        save_kwargs: dict = {"format": fmt}
        if fmt == "JPEG":
            save_kwargs.update(quality=92, optimize=True, progressive=True)
        # Note: we deliberately pass no exif/icc_profile -> stripped.
        img.save(buffer, **save_kwargs)
        width, height = img.size
        clean = buffer.getvalue()

    return ImageInfo(
        data=clean,
        width=width,
        height=height,
        sha256=hashlib.sha256(clean).hexdigest(),
        format=fmt,
        had_exif=had_exif,
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_image(data: bytes) -> Optional[str]:
    """Return an error string if ``data`` is not a usable image, else None."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
        return None
    except Exception as exc:  # pragma: no cover - defensive
        return f"Unreadable image: {exc}"
