"""Enrollment service.

Hard requirements enforced here:
  * an active, non-revoked consent record must exist for the identity;
  * the enrollment image must contain EXACTLY ONE face;
  * the face must pass quality checks (blur, lighting, pose, size).

Anything short of that raises ``EnrollmentError`` — no template is created.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import numpy as np
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import ConsentRecord, Enrollment, Identity
from app.services.crypto import encrypt_embedding
from app.services.face_engine import get_face_engine
from app.services.quality import QualityThresholds, crop_face, evaluate_face

CONSENT_TEXT_VERSION = "2026-01"


class EnrollmentError(Exception):
    def __init__(self, message: str, *, reasons: Optional[list[str]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.reasons = reasons or []


class ConsentError(Exception):
    pass


def active_consent(db: Session, tenant_id: str, identity_id: str) -> Optional[ConsentRecord]:
    rows = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == tenant_id,
            ConsentRecord.identity_id == identity_id,
            ConsentRecord.revoked_at.is_(None),
        )
    ).scalars().all()
    for rec in rows:
        if rec.is_active():
            return rec
    return None


def enroll_identity(
    db: Session,
    *,
    tenant_id: str,
    identity: Identity,
    image_rgb: Image.Image,
    user_id: Optional[str] = None,
    source_media_id: Optional[str] = None,
    thresholds: Optional[QualityThresholds] = None,
) -> Enrollment:
    if identity.deleted_at is not None:
        raise ConsentError("Cannot enroll a deleted identity.")

    consent = active_consent(db, tenant_id, identity.id)
    if consent is None:
        raise ConsentError("No active consent record for this identity. Explicit consent is required.")

    engine = get_face_engine()
    arr = np.asarray(image_rgb.convert("RGB"))
    faces = engine.detect(arr, want_embeddings=True)

    if len(faces) == 0:
        raise EnrollmentError("No face detected in the enrollment image.")
    if len(faces) > 1:
        raise EnrollmentError(
            f"EXACTLY ONE face is required, but {len(faces)} were detected. "
            "Upload a photo containing only the consenting person."
        )

    face = faces[0]
    crop = crop_face(image_rgb, face.bbox)
    quality = evaluate_face(
        crop,
        (int(face.bbox[2] - face.bbox[0]), int(face.bbox[3] - face.bbox[1])),
        face.landmarks,
        thresholds,
    )
    if not quality.passed:
        raise EnrollmentError(
            "Enrollment image failed quality checks.", reasons=quality.reasons
        )

    emb = face.embedding
    if emb is None:
        emb = engine.embed_face(np.asarray(crop.convert("RGB")))

    enrollment = Enrollment(
        tenant_id=tenant_id,
        identity_id=identity.id,
        consent_record_id=consent.id,
        status="active",
        quality_score=quality.score,
        quality_detail=json.dumps(quality.to_dict()),
        embedding_encrypted=encrypt_embedding(emb),
        embedding_dim=int(np.asarray(emb).size),
        model_name=engine.model_info()["name"],
        source_media_id=source_media_id,
        created_by=user_id,
    )
    db.add(enrollment)
    db.flush()
    return enrollment


def purge_identity(db: Session, tenant_id: str, identity: Identity) -> None:
    """Irreversibly delete an identity and every dependent record."""
    # ORM cascades remove consents + enrollments; recognition results referencing
    # the identity are anonymised (identity_id/candidate_name cleared).
    from app.models.media import RecognitionResult

    db.execute(
        RecognitionResult.__table__.update()
        .where(RecognitionResult.tenant_id == tenant_id, RecognitionResult.identity_id == identity.id)
        .values(identity_id=None, candidate_name="[redacted]", status="no_match", manual_review_required=True)
    )
    db.delete(identity)
    db.flush()


def consent_evidence_hash(identity_name: str, purpose: str, expires: datetime, retention: datetime) -> str:
    import hashlib

    payload = f"{identity_name}|{purpose}|{expires.isoformat()}|{retention.isoformat()}|{CONSENT_TEXT_VERSION}"
    return hashlib.sha256(payload.encode()).hexdigest()
