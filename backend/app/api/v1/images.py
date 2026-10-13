"""Image detection + optional consent-gated recognition endpoints."""
from __future__ import annotations

import io
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models.media import FaceDetection, MediaAsset
from app.models.user import User
from app.schemas.media import (
    BoundingBox,
    DetectionRead,
    DetectionResponse,
    MediaRead,
)
from app.services.audit import record as audit_record
from app.services.pipeline import run_image_pipeline
from app.services.storage import get_storage
from app.services.uploads import UploadRejected, validate_image_upload

router = APIRouter()

PRIVACY_NOTICE = (
    "This tool performs face DETECTION by default. Recognition is optional, only searches a local "
    "consent-based gallery, and never asserts identity — results require manual human review."
)


def _store_and_run(
    db: Session,
    *,
    request: Request,
    user: User,
    file: UploadFile,
    mode: str,
    threshold: float | None,
    top_k: int,
) -> DetectionResponse:
    raw = file.file.read()
    try:
        validated = validate_image_upload(raw, file.content_type or "application/octet-stream")
    except UploadRejected as exc:
        audit_record(
            db, tenant_id=user.tenant_id, action=f"image.{mode}.rejected", actor_user_id=user.id,
            actor_email=user.email, outcome="rejected", detail={"reason": exc.message}, request=request,
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)

    storage = get_storage()
    media = MediaAsset(
        tenant_id=user.tenant_id,
        kind="image",
        original_filename=file.filename or "upload",
        content_type=file.content_type or "image/jpeg",
        size_bytes=len(raw),
        sha256=validated.info.sha256,
        exif_stripped=True,
        width=validated.info.width,
        height=validated.info.height,
        created_by=user.id,
        status="processing",
    )
    db.add(media)
    db.flush()

    upload_key = f"uploads/{user.tenant_id}/{media.id}/original.jpg"
    storage.put(upload_key, validated.info.data, "image/jpeg")
    media.storage_key = upload_key

    result = run_image_pipeline(
        db,
        tenant_id=user.tenant_id,
        media=media,
        image_rgb=validated.image,
        mode=mode,
        threshold=threshold,
        top_k=top_k,
        user_id=user.id,
    )

    result_key = f"results/{user.tenant_id}/{media.id}/annotated.jpg"
    storage.put(result_key, result.annotated_bytes or validated.info.data, "image/jpeg")
    media.result_key = result_key
    db.commit()

    audit_record(
        db, tenant_id=user.tenant_id, action=f"image.{mode}", actor_user_id=user.id,
        actor_email=user.email, resource_type="media", resource_id=media.id,
        detail={"face_count": len(result.faces), "mode": mode}, request=request,
    )

    detections = [
        DetectionRead(
            id=f"det-{i}",
            bbox=BoundingBox(x1=f.bbox[0], y1=f.bbox[1], x2=f.bbox[2], y2=f.bbox[3]),
            confidence=f.confidence,
            landmarks=f.landmarks,
            quality=f.quality,
        )
        for i, f in enumerate(result.faces)
    ]

    return DetectionResponse(
        media_id=media.id,
        kind="image",
        face_count=len(result.faces),
        processing_ms=result.processing_ms,
        width=media.width,
        height=media.height,
        mode=mode,
        detections=detections,
        annotated_url=f"{settings.api_v1_prefix}/images/{media.id}/annotated",
        recognition=result.recognition or None,
        notices=[PRIVACY_NOTICE, *result.notices],
    )


@router.post("/detect", response_model=DetectionResponse, summary="Detect faces (no identity)")
def detect_image(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> DetectionResponse:
    return _store_and_run(db, request=request, user=user, file=file, mode="detection", threshold=None, top_k=3)


@router.post(
    "/recognize",
    response_model=DetectionResponse,
    summary="Detect + search the consented gallery (advisory candidates only)",
)
def recognize_image(
    request: Request,
    file: UploadFile = File(...),
    threshold: float | None = Form(default=None),
    top_k: int = Form(default=3),
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> DetectionResponse:
    if not settings.recognition_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Recognition is disabled.")
    if threshold is not None and not (0.0 <= threshold <= 1.0):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="threshold must be 0..1")
    return _store_and_run(db, request=request, user=user, file=file, mode="recognition", threshold=threshold, top_k=top_k)


@router.get("", response_model=list[MediaRead], summary="List your image uploads")
def list_images(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MediaAsset]:
    rows = db.execute(
        select(MediaAsset)
        .where(MediaAsset.tenant_id == user.tenant_id, MediaAsset.kind == "image")
        .order_by(MediaAsset.created_at.desc())
        .limit(100)
    ).scalars().all()
    for m in rows:
        m.annotated_url = f"{settings.api_v1_prefix}/images/{m.id}/annotated" if m.result_key else None
    return list(rows)


def _get_media(db: Session, tenant_id: str, media_id: str) -> MediaAsset:
    media = db.get(MediaAsset, media_id)
    if media is None or media.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    return media


@router.get("/{media_id}", response_model=MediaRead, summary="Image detail")
def get_image(media_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MediaAsset:
    media = _get_media(db, user.tenant_id, media_id)
    media.annotated_url = f"{settings.api_v1_prefix}/images/{media_id}/annotated" if media.result_key else None
    return media


@router.get("/{media_id}/annotated", summary="Download annotated image")
def get_annotated(media_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    media = _get_media(db, user.tenant_id, media_id)
    if not media.result_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotated result not ready")
    data = get_storage().get(media.result_key)
    return StreamingResponse(io.BytesIO(data), media_type="image/jpeg",
                             headers={"Content-Disposition": f'attachment; filename="jarvas-{media_id}.jpg"'})


@router.get("/{media_id}/detections", summary="Raw detections JSON for an image")
def get_detections(media_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    media = _get_media(db, user.tenant_id, media_id)
    rows = db.execute(
        select(FaceDetection).where(
            FaceDetection.tenant_id == user.tenant_id, FaceDetection.media_id == media_id
        )
    ).scalars().all()
    return {
        "media_id": media_id,
        "face_count": media.face_count,
        "detections": [
            {
                "id": d.id,
                "bbox": [d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2],
                "confidence": d.detection_confidence,
                "landmarks": json.loads(d.landmarks_json or "[]"),
                "quality": json.loads(d.quality_json or "{}"),
            }
            for d in rows
        ],
    }
