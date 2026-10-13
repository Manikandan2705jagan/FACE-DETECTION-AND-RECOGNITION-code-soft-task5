"""Celery tasks: async video processing and retention sweeps."""
from __future__ import annotations

from app.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.media import MediaAsset, VideoJob
from app.services.storage import get_storage
from app.services.video import process_video
from app.services import retention

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.process_video_job", bind=True)
def process_video_job(self, job_id: str) -> dict:  # pragma: no cover - requires worker
    db = SessionLocal()
    try:
        job = db.get(VideoJob, job_id)
        if job is None:
            logger.error("Video job %s not found", job_id)
            return {"status": "not_found"}
        media = db.get(MediaAsset, job.media_id)
        if media is None:
            job.status = "failed"
            job.error = "Media asset missing"
            db.commit()
            return {"status": "failed"}
        data = get_storage().get(media.storage_key)
        report = process_video(db, job=job, media=media, video_bytes=data, sample_fps=job.sample_fps)
        # Persist report to results storage.
        import json

        report_key = f"results/{media.tenant_id}/{media.id}/report.json"
        get_storage().put(report_key, json.dumps(report).encode(), "application/json")
        media.report_key = report_key
        db.commit()
        return {"status": "completed", "job_id": job_id}
    finally:
        db.close()


@celery_app.task(name="app.tasks.retention_sweep")
def retention_sweep() -> dict:  # pragma: no cover - requires worker
    db = SessionLocal()
    try:
        bio = retention.purge_biometrics(db)
        media = retention.purge_expired_media(db)
        return {"biometrics": bio, "media": media}
    finally:
        db.close()
