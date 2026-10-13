"""Face-image quality gate.

Checks blur, lighting, pose and face size. Enrollment is refused unless every
check passes, so templates are only created from clear, single, well-lit faces.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

import numpy as np
from PIL import Image

try:  # pragma: no cover - cv2 optional at runtime
    import cv2

    _HAS_CV2 = True
except Exception:  # pragma: no cover
    _HAS_CV2 = False


@dataclass
class QualityThresholds:
    min_face_size_px: int = 80
    min_blur_score: float = 0.35
    min_lighting_score: float = 0.35
    min_pose_score: float = 0.35
    min_overall_score: float = 0.5


@dataclass
class QualityResult:
    passed: bool
    score: float
    blur: float
    lighting: float
    pose: float
    face_size_px: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _laplacian_variance(gray: np.ndarray) -> float:
    if _HAS_CV2:
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    # Vectorised 4-neighbour Laplacian fallback.
    h, w = gray.shape
    if h < 3 or w < 3:
        return 0.0
    lap = (
        gray[0:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, 0:-2]
        + gray[1:-1, 2:]
        - 4.0 * gray[1:-1, 1:-1]
    )
    return float(lap.var())


def _blur_score(gray: np.ndarray) -> float:
    variance = _laplacian_variance(gray)
    # ~500+ variance is crisp; map with a soft saturating curve.
    return float(min(1.0, variance / 500.0))


def _lighting_score(gray: np.ndarray) -> float:
    mean = float(gray.mean())  # 0..255
    std = float(gray.std())
    # Ideal brightness around 128; penalise dark/blown-out.
    brightness = 1.0 - min(1.0, abs(mean - 128.0) / 128.0)
    # Reasonable contrast std around 50+.
    contrast = min(1.0, std / 55.0)
    return float(max(0.0, 0.6 * brightness + 0.4 * contrast))


def _pose_score(landmarks: Optional[Sequence[Sequence[float]]]) -> float:
    """Estimate frontalness from the 5-point InsightFace landmarks."""
    if not landmarks or len(landmarks) < 3:
        return 0.5  # unknown -> neutral, not fatal on its own
    pts = np.asarray(landmarks, dtype=np.float64)
    left_eye, right_eye, nose = pts[0], pts[1], pts[2]
    eye_mid = (left_eye + right_eye) / 2.0
    eye_dist = float(np.linalg.norm(right_eye - left_eye)) or 1.0
    # Yaw: horizontal nose offset from eye midpoint, normalised by eye distance.
    yaw = abs(float(nose[0] - eye_mid[0]) / eye_dist)
    yaw_score = max(0.0, 1.0 - yaw)
    # Roll: eye line angle.
    roll = abs(float(np.degrees(np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0]))))
    roll_score = max(0.0, 1.0 - min(1.0, roll / 30.0))
    # Pitch heuristic: vertical nose offset relative to eye distance.
    pitch = abs(float(nose[1] - eye_mid[1]) / eye_dist)
    pitch_score = max(0.0, 1.0 - abs(pitch - 0.6) / 0.6)
    return float(max(0.0, 0.45 * yaw_score + 0.25 * roll_score + 0.30 * pitch_score))


def evaluate_face(
    face_image: Image.Image,
    bbox_wh: tuple[int, int],
    landmarks: Optional[Sequence[Sequence[float]]] = None,
    thresholds: Optional[QualityThresholds] = None,
) -> QualityResult:
    th = thresholds or QualityThresholds()
    reasons: list[str] = []

    gray = np.asarray(face_image.convert("L"), dtype=np.float64)
    blur = _blur_score(gray)
    lighting = _lighting_score(gray)
    pose = _pose_score(landmarks)
    face_size = int(min(bbox_wh))

    if face_size < th.min_face_size_px:
        reasons.append(f"Face too small ({face_size}px < {th.min_face_size_px}px).")
    if blur < th.min_blur_score:
        reasons.append("Image appears blurry or out of focus.")
    if lighting < th.min_lighting_score:
        reasons.append("Lighting is too dark, too bright, or too flat.")
    if pose < th.min_pose_score:
        reasons.append("Face is not sufficiently frontal (head pose).")

    score = float(0.35 * blur + 0.25 * lighting + 0.25 * pose + 0.15 * min(1.0, face_size / 200.0))
    if face_size < th.min_face_size_px:
        score *= 0.5
    passed = not reasons and score >= th.min_overall_score

    return QualityResult(
        passed=passed,
        score=round(score, 4),
        blur=round(blur, 4),
        lighting=round(lighting, 4),
        pose=round(pose, 4),
        face_size_px=face_size,
        reasons=reasons,
    )


def crop_face(image: Image.Image, bbox: Sequence[float], margin: float = 0.15) -> Image.Image:
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    mx, my = w * margin, h * margin
    box = (
        max(0, int(x1 - mx)),
        max(0, int(y1 - my)),
        min(image.width, int(x2 + mx)),
        min(image.height, int(y2 + my)),
    )
    return image.crop(box)
