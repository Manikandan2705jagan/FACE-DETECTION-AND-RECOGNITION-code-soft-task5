"""High-level detection / recognition orchestration for still images."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import Identity
from app.models.media import FaceDetection, MediaAsset, RecognitionResult
from app.services import gallery as gallery_service
from app.services.annotate import annotate_faces
from app.services.face_engine import DetectedFace, get_face_engine
from app.services.quality import crop_face, evaluate_face


@dataclass
class FaceOut:
    bbox: tuple[float, float, float, float]
    confidence: float
    landmarks: list[list[float]]
    quality: dict = field(default_factory=dict)


@dataclass
class ImagePipelineResult:
    mode: str
    faces: list[FaceOut]
    processing_ms: float
    annotated_bytes: Optional[bytes]
    recognition: list[dict] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)


def _detect_faces(image_rgb: Image.Image, want_embeddings: bool) -> tuple[list[DetectedFace], float]:
    engine = get_face_engine()
    arr = np.asarray(image_rgb.convert("RGB"))
    start = time.perf_counter()
    faces = engine.detect(arr, want_embeddings=want_embeddings)
    elapsed = (time.perf_counter() - start) * 1000.0
    return faces, elapsed


def run_image_pipeline(
    db: Session,
    *,
    tenant_id: str,
    media: MediaAsset,
    image_rgb: Image.Image,
    mode: str = "detection",
    threshold: Optional[float] = None,
    top_k: int = 3,
    user_id: Optional[str] = None,
    persist: bool = True,
) -> ImagePipelineResult:
    want_embeddings = mode == "recognition"
    faces, elapsed_ms = _detect_faces(image_rgb, want_embeddings)

    outputs: list[FaceOut] = []
    for face in faces:
        crop = crop_face(image_rgb, face.bbox)
        quality = evaluate_face(crop, (int(face.bbox[2] - face.bbox[0]), int(face.bbox[3] - face.bbox[1])),
                                face.landmarks)
        outputs.append(
            FaceOut(
                bbox=face.bbox,
                confidence=round(face.confidence, 4),
                landmarks=face.landmarks,
                quality=quality.to_dict(),
            )
        )

    notices: list[str] = []
    recognition: list[dict] = []

    if mode == "recognition":
        engine = get_face_engine()
        notices.append(
            "Recognition results are advisory candidates only and require manual human review. "
            "Similarity scores are not proof of identity."
        )
        for face in faces:
            emb = face.embedding
            if emb is None:
                crop = crop_face(image_rgb, face.bbox)
                emb = engine.embed_face(np.asarray(crop.convert("RGB")))
            candidates = gallery_service.search(db, tenant_id, emb, threshold=threshold, top_k=top_k)
            for c in candidates:
                recognition.append(
                    {
                        "identity_id": c.identity_id or None,
                        "candidate_name": c.name or None,
                        "cosine_similarity": c.cosine_similarity,
                        "threshold": c.threshold,
                        "manual_review_required": c.manual_review_required,
                        "status": c.status,
                    }
                )

    labels = None
    if mode == "recognition" and recognition:
        top = recognition[0]
        if top.get("status") == "candidate" and top.get("candidate_name"):
            labels = [f"Candidate: {top['candidate_name']} (review)"]

    annotated = annotate_faces(image_rgb, faces, labels=labels)

    if persist:
        media.face_count = len(faces)
        media.processing_ms = round(elapsed_ms, 2)
        media.status = "completed"
        for out in outputs:
            db.add(
                FaceDetection(
                    tenant_id=tenant_id,
                    media_id=media.id,
                    bbox_x1=out.bbox[0], bbox_y1=out.bbox[1],
                    bbox_x2=out.bbox[2], bbox_y2=out.bbox[3],
                    detection_confidence=out.confidence,
                    landmarks_json=json.dumps(out.landmarks),
                    quality_json=json.dumps(out.quality),
                )
            )
        for rec in recognition:
            db.add(
                RecognitionResult(
                    tenant_id=tenant_id,
                    media_id=media.id,
                    identity_id=rec["identity_id"],
                    candidate_name=rec["candidate_name"],
                    cosine_similarity=rec["cosine_similarity"],
                    threshold=rec["threshold"],
                    manual_review_required=rec["manual_review_required"],
                    status=rec["status"],
                    created_by=user_id,
                )
            )
        db.flush()

    return ImagePipelineResult(
        mode=mode,
        faces=outputs,
        processing_ms=round(elapsed_ms, 2),
        annotated_bytes=annotated,
        recognition=recognition,
        notices=notices,
    )
