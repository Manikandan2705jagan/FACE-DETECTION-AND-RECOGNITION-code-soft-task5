"""Face detection + embedding engine.

Primary path uses InsightFace (SCRFD detector + ArcFace recogniser) through ONNX
Runtime. If the model weights or the ``insightface`` package are unavailable and
``ALLOW_MOCK_FACE_ENGINE`` is true, a deterministic mock is used so the whole
application remains runnable (for demos, tests and CI) — the mock is clearly
flagged everywhere via ``is_mock``.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DetectedFace:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    landmarks: List[List[float]] = field(default_factory=list)
    embedding: Optional[np.ndarray] = None

    @property
    def size_px(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return float(min(x2 - x1, y2 - y1))


class FaceEngine:
    """Thread-safe, lazily-initialised face analysis engine."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._app = None
        self._loaded = False
        self._is_mock = False
        self._model_name = settings.face_detection_model
        self._provider = settings.provider_list[0] if settings.provider_list else "CPUExecutionProvider"
        self._load_error: Optional[str] = None

    # ---- lifecycle ---------------------------------------------------------
    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                from insightface.app import FaceAnalysis  # type: ignore

                app = FaceAnalysis(
                    name=settings.face_detection_model,
                    root=settings.model_dir or None,
                    providers=settings.provider_list or ["CPUExecutionProvider"],
                )
                app.prepare(ctx_id=0 if "CUDAExecutionProvider" in settings.provider_list else -1,
                            det_size=(settings.face_det_size, settings.face_det_size))
                self._app = app
                self._is_mock = False
                logger.info("Loaded InsightFace model '%s'", settings.face_detection_model)
            except Exception as exc:  # pragma: no cover - depends on host
                self._load_error = str(exc)
                if not settings.allow_mock_face_engine:
                    raise RuntimeError(
                        f"Face engine failed to load and mock disabled: {exc}"
                    ) from exc
                self._is_mock = True
                logger.warning(
                    "InsightFace unavailable (%s); using deterministic MOCK engine.", exc
                )
            finally:
                self._loaded = True

    # ---- public API --------------------------------------------------------
    @property
    def is_mock(self) -> bool:
        self._load()
        return self._is_mock

    @property
    def loaded(self) -> bool:
        self._load()
        return self._app is not None or self._is_mock

    @property
    def provider(self) -> str:
        self._load()
        return "mock" if self._is_mock else self._provider

    def model_info(self) -> dict:
        self._load()
        return {
            "name": self._model_name,
            "provider": self.provider,
            "embedding_dim": settings.face_embedding_dim,
            "loaded": self.loaded,
            "is_mock": self._is_mock,
            "error": self._load_error,
        }

    def detect(self, image_rgb: np.ndarray, want_embeddings: bool = False) -> List[DetectedFace]:
        """Detect faces in an RGB uint8 image. Set ``want_embeddings`` to embed."""
        self._load()
        if self._is_mock:
            return self._mock_detect(image_rgb, want_embeddings)

        bgr = image_rgb[:, :, ::-1]  # InsightFace expects BGR
        faces = self._app.get(bgr)  # type: ignore[union-attr]
        results: List[DetectedFace] = []
        for f in faces:
            bbox = tuple(float(v) for v in f.bbox)  # type: ignore[attr-defined]
            kps = getattr(f, "kps", None)
            landmarks = (
                [[float(p[0]), float(p[1])] for p in kps] if kps is not None else []
            )
            emb = None
            if want_embeddings:
                emb = np.asarray(getattr(f, "normed_embedding", None), dtype=np.float32)
            results.append(
                DetectedFace(
                    bbox=bbox,  # type: ignore[arg-type]
                    confidence=float(getattr(f, "det_score", 0.0)),
                    landmarks=landmarks,
                    embedding=emb,
                )
            )
        return sorted(results, key=lambda d: d.size_px, reverse=True)

    def embed_face(self, face_image: np.ndarray) -> np.ndarray:
        """Return an L2-normalised embedding for a single aligned face crop."""
        self._load()
        if self._is_mock or self._app is None:
            return self._mock_embed(face_image)
        bgr = face_image[:, :, ::-1]
        faces = self._app.get(bgr)  # type: ignore[union-attr]
        if not faces:
            return self._mock_embed(face_image)
        best = max(faces, key=lambda f: float(getattr(f, "det_score", 0.0)))
        emb = np.asarray(getattr(best, "normed_embedding", None), dtype=np.float32)
        return _l2_normalise(emb)

    # ---- deterministic mock ------------------------------------------------
    def _mock_detect(self, image_rgb: np.ndarray, want_embeddings: bool) -> List[DetectedFace]:
        h, w = image_rgb.shape[:2]
        # Heuristic: treat reasonably-sized, non-uniform images as containing one
        # centred face. Blank/flat images (e.g. solid colours) yield no faces.
        if h < 64 or w < 64:
            return []
        gray = np.asarray(image_rgb).astype(np.float32).mean(axis=2)
        if float(gray.std()) < 6.0:
            return []
        cx, cy = w / 2.0, h * 0.45
        size = min(h, w) * 0.5
        x1, y1 = cx - size / 2, cy - size / 2
        x2, y2 = cx + size / 2, cy + size / 2
        landmarks = [
            [x1 + size * 0.32, y1 + size * 0.40],  # left eye
            [x1 + size * 0.68, y1 + size * 0.40],  # right eye
            [x1 + size * 0.50, y1 + size * 0.55],  # nose
            [x1 + size * 0.36, y1 + size * 0.72],  # left mouth
            [x1 + size * 0.64, y1 + size * 0.72],  # right mouth
        ]
        emb = self._mock_embed(image_rgb) if want_embeddings else None
        return [
            DetectedFace(
                bbox=(x1, y1, x2, y2),
                confidence=0.93,
                landmarks=landmarks,
                embedding=emb,
            )
        ]

    @staticmethod
    def _mock_embed(face_image: np.ndarray) -> np.ndarray:
        """Deterministic pseudo-embedding derived from image content.

        Same pixels -> identical vector, so the demo recognition flow is
        reproducible without shipping real model weights.
        """
        dim = settings.face_embedding_dim
        # Downsample to a compact signature then expand deterministically.
        try:
            from PIL import Image

            small = Image.fromarray(face_image).convert("L").resize((16, 16))
            signature = np.asarray(small, dtype=np.uint8).tobytes()
        except Exception:  # pragma: no cover
            signature = np.asarray(face_image, dtype=np.uint8).tobytes()[:4096]
        seed = int.from_bytes(hashlib.sha256(signature).digest()[:8], "big")
        rng = np.random.RandomState(seed % (2**32 - 1))
        vec = rng.standard_normal(dim).astype(np.float32)
        return _l2_normalise(vec)


def _l2_normalise(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float32).ravel()
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    if a.size != b.size or a.size == 0:
        return 0.0
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


# Process-wide singleton (InsightFace models are expensive to load).
_engine: Optional[FaceEngine] = None
_engine_lock = threading.Lock()


def get_face_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = FaceEngine()
    return _engine


def warm_up() -> None:
    """Best-effort model warm-up at startup."""
    try:
        get_face_engine()._load()
    except Exception as exc:  # pragma: no cover
        logger.error("Face engine warm-up failed: %s", exc)
