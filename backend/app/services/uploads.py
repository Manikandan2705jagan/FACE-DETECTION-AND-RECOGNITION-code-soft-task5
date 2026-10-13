"""Upload validation: MIME/size/format checks + EXIF stripping."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from app.core.config import settings
from app.services.exif import ImageInfo, strip_exif, verify_image


class UploadRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ValidatedImage:
    info: ImageInfo
    image: Image.Image


def validate_image_upload(data: bytes, content_type: str) -> ValidatedImage:
    if not data:
        raise UploadRejected("Empty upload.")
    if content_type not in settings.image_types:
        raise UploadRejected(
            f"Unsupported image type '{content_type}'. Allowed: {', '.join(settings.image_types)}"
        )
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadRejected(f"File exceeds maximum size of {settings.max_upload_mb} MB.")

    error = verify_image(data)
    if error:
        raise UploadRejected(error)

    info = strip_exif(data, content_type)
    image = Image.open(_bytes_io(info.data)).convert("RGB")
    return ValidatedImage(info=info, image=image)


def validate_video_upload(data: bytes, content_type: str) -> None:
    if not data:
        raise UploadRejected("Empty upload.")
    if content_type not in settings.video_types:
        raise UploadRejected(
            f"Unsupported video type '{content_type}'. Allowed: {', '.join(settings.video_types)}"
        )
    max_bytes = settings.video_max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadRejected(f"Video exceeds maximum size of {settings.video_max_upload_mb} MB.")


def _bytes_io(data: bytes):
    import io

    return io.BytesIO(data)
