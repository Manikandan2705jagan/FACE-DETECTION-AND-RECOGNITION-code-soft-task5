"""Bounding-box / landmark annotation rendering."""
from __future__ import annotations

import io
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

from app.services.face_engine import DetectedFace

_BOX_COLOR = (34, 211, 238)      # cyan-400
_LABEL_BG = (15, 23, 42, 220)    # navy
_LABEL_FG = (224, 242, 254)
_LANDMARK = (45, 212, 191)       # teal-400


def _font(size: int = 14) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def annotate_faces(
    image_rgb: Image.Image,
    faces: Iterable[DetectedFace],
    labels: Sequence[str] | None = None,
    show_landmarks: bool = True,
    show_confidence: bool = True,
) -> bytes:
    """Return JPEG bytes with boxes, landmarks and labels drawn on top."""
    base = image_rgb.convert("RGB").copy()
    draw = ImageDraw.Draw(base, "RGBA")
    font = _font(max(12, base.width // 60))
    labels = list(labels) if labels else []

    for idx, face in enumerate(faces):
        x1, y1, x2, y2 = face.bbox
        draw.rectangle([x1, y1, x2, y2], outline=_BOX_COLOR, width=max(2, base.width // 400))

        if show_landmarks:
            for point in face.landmarks:
                px, py = point[0], point[1]
                r = max(2, base.width // 300)
                draw.ellipse([px - r, py - r, px + r, py + r], fill=_LANDMARK)

        text_parts = []
        if labels and idx < len(labels):
            text_parts.append(labels[idx])
        if show_confidence:
            text_parts.append(f"{face.confidence * 100:.0f}%")
        text = "  ".join(text_parts)

        if text:
            tb = draw.textbbox((x1, y1), text, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            ty = max(0, y1 - th - 8)
            draw.rectangle([x1, ty, x1 + tw + 10, ty + th + 8], fill=_LABEL_BG)
            draw.text((x1 + 5, ty + 4), text, fill=_LABEL_FG, font=font)

    buffer = io.BytesIO()
    base.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()
