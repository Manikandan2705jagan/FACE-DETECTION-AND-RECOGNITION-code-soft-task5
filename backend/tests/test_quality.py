"""Quality-gate unit tests."""
from __future__ import annotations

import numpy as np
from PIL import Image

from app.seed import synthetic_face
from app.services.quality import QualityThresholds, crop_face, evaluate_face


def test_blank_image_fails_quality():
    blank = Image.new("RGB", (128, 128), (10, 10, 10))
    result = evaluate_face(blank, (128, 128), landmarks=None)
    assert result.passed is False
    assert result.reasons


def test_synthetic_face_passes_size_check():
    img = synthetic_face(seed=7, size=512)
    result = evaluate_face(img, (300, 320), landmarks=None,
                           thresholds=QualityThresholds(min_pose_score=0.0, min_lighting_score=0.0))
    assert result.face_size_px == 300
    assert result.blur >= 0.0


def test_tiny_face_is_rejected():
    img = synthetic_face(seed=8, size=512)
    result = evaluate_face(img, (40, 40), landmarks=None)
    assert result.passed is False
    assert any("small" in r.lower() for r in result.reasons)


def test_crop_face_bounds():
    img = synthetic_face(seed=9, size=256)
    crop = crop_face(img, (20, 20, 100, 100))
    assert crop.width > 0 and crop.height > 0
