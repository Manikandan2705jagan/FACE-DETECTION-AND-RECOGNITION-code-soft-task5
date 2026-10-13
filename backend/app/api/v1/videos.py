"""Video upload + background face-detection jobs (detection-only)."""
from __future__ import annotations

import io
import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.core.logging import get_logger
from app.core.security import Role
from app.db.session import SessionLocal, get_db
from app.models.media import MediaAsset, VideoJob
from app.models.user import User
from app.schemas.media import MediaRead, TimelinePoint, VideoJobRead, VideoReport
from app.services.audit import record as audit_record
from app.services.storage import get_storage
from app.services.uploads import UploadRejected, validate_video_upload
from app.services.video import estimate_sample_count, process_video

router = APIRouter()
logger = get_logger(__name__)

PRIVACY_NOTICE = (
    "Video processing is detection-only: anonymous face counts per sampled frame. No identities, "
    "no tracking, no demographic or emotion analysis."
)


def _run_job_sync(job_id: str) -> None:
    """Background-task entrypoint using its own DB session."""
    db = SessionLocal()
    try:
        job = db.get(VideoJob, job_id)
        if job is None:
            return
        media = db.get(MediaAsset, job.media_id)
        if media is None:
            job.status = "failed"
            job.error = "Media asset missing"
            db.commit()
            return
        try:
            data = get_storage().get(media.storage_key)
            report = process_video(db, job=job, media=media, video_bytes=data, sample_fps=job.sample_fps)
            report_key = f"results/{media.tenant_id}/{media.id}/video-report.json"
            get_storage().put(report_key, json.dumps(report).encode(), "application/json")
            media.report_key = report_key
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("Video job %s failed: %s", job_id, exc)
            job.status = "failed"
            job.error = str(exc)
            db.commit()
    finally:
        db.close()


@router.post("", response_model=VideoJobRead, summary="Upload a video and start a detection job")
def upload_video(
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    sample_fps: float = Form(default=None),
    process_async: bool = Form(default=False),
    user: User = Depends(require_role(Role.VIEWER)),
    db: Session = Depends(get_db),
) -> VideoJob:
    raw = file.file.read()
    try:
        validate_video_upload(raw, file.content_type or "application/octet-stream")
    except UploadRejected as exc:
        audit_record(
            db, tenant_id=user.tenant_id, action="video.upload.rejected", actor_user_id=user.id,
            actor_email=user.email, outcome="rejected", detail={"reason": exc.message}, request=request,
        )
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)

    fps = sample_fps or settings.video_default_sample_fps
    fps = max(0.1, min(10.0, float(fps)))

    try:
        estimated, duration = estimate_sample_count(raw, fps)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Could not read video: {exc}")

    if duration > settings.video_max_duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Video exceeds maximum duration of {settings.video_max_duration_seconds}s.",
        )

    storage = get_storage()
    media = MediaAsset(
        tenant_id=user.tenant_id,
        kind="video",
        original_filename=file.filename or "video.mp4",
        content_type=file.content_type or "video/mp4",
        size_bytes=len(raw),
        status="processing",
        exif_stripped=True,
        created_by=user.id,
    )
    db.add(media)
    db.flush()

    video_key = f"uploads/{user.tenant_id}/{media.id}/source{_ext(file.content_type)}"
    storage.put(video_key, raw, file.content_type or "video/mp4")
    media.storage_key = video_key

    job = VideoJob(
        tenant_id=user.tenant_id,
        media_id=media.id,
        status="queued",
        sample_fps=fps,
        frames_total=estimated,
        duration_seconds=round(duration, 2),
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    audit_record(
        db, tenant_id=user.tenant_id, action="video.upload", actor_user_id=user.id,
        actor_email=user.email, resource_type="video_job", resource_id=job.id,
        detail={"sample_fps": fps, "estimated_frames": estimated}, request=request,
    )

    if process_async:
        try:
            from app.tasks import process_video_job

            process_video_job.delay(job.id)
        except Exception as exc:  # broker unavailable -> fall back to inline
            logger.warning("Celery unavailable (%s); processing inline.", exc)
            background.add_task(_run_job_sync, job.id)
    else:
        background.add_task(_run_job_sync, job.id)

    return job


def _ext(content_type: str | None) -> str:
    return {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
    }.get(content_type or "", ".mp4")


@router.get("", response_model=list[VideoJobRead], summary="List video jobs")
def list_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[VideoJob]:
    return list(
        db.execute(
            select(VideoJob).where(VideoJob.tenant_id == user.tenant_id).order_by(VideoJob.created_at.desc()).limit(100)
        ).scalars().all()
    )


def _get_job(db: Session, tenant_id: str, job_id: str) -> VideoJob:
    job = db.get(VideoJob, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video job not found")
    return job


@router.get("/{job_id}", response_model=VideoJobRead, summary="Video job status / progress")
def get_job(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> VideoJob:
    return _get_job(db, user.tenant_id, job_id)


@router.get("/{job_id}/report", response_model=VideoReport, summary="Face-count timeline report")
def get_report(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> VideoReport:
    job = _get_job(db, user.tenant_id, job_id)
    media = db.get(MediaAsset, job.media_id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    media.annotated_url = None
    timeline: list[TimelinePoint] = []
    if media.report_key:
        try:
            report = json.loads(get_storage().get(media.report_key).decode())
            timeline = [TimelinePoint(**p) for p in report.get("timeline", [])]
        except Exception:  # pragma: no cover
            timeline = []
    return VideoReport(
        job=VideoJobRead.model_validate(job),
        media=MediaRead.model_validate(media),
        timeline=timeline,
        notes=[PRIVACY_NOTICE],
    )


@router.get("/{job_id}/report.json", summary="Download the video report as JSON")
def download_report(job_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _get_job(db, user.tenant_id, job_id)
    media = db.get(MediaAsset, job.media_id)
    if media is None or not media.report_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not ready")
    data = get_storage().get(media.report_key)
    return StreamingResponse(
        io.BytesIO(data), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="jarvas-video-{job_id}.json"'},
    )
