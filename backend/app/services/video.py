"""Video processing: frame sampling, face counting, timeline + report.

Uses OpenCV for decoding. The heavy lifting runs in a background Celery worker
(see ``app.tasks``); a synchronous fallback is provided so the feature works even
when no worker is running (dev/demo).
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Callable, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.media import FaceDetection, MediaAsset, VideoJob
from app.services.face_engine import get_face_engine

logger = get_logger(__name__)

ProgressHook = Callable[[int, int, int], None]  # frames_processed, frames_total, faces_so_far


def _open_video(path: str):
    try:
        import cv2  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("OpenCV is required for video processing") from exc
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError("Could not open video file (unsupported codec?)")
    return cap


def process_video(
    db: Session,
    *,
    job: VideoJob,
    media: MediaAsset,
    video_bytes: bytes,
    sample_fps: float,
    progress_hook: Optional[ProgressHook] = None,
    max_persisted_detections: int = 2000,
) -> dict:
    """Sample frames, detect faces, persist detections and build a report."""
    engine = get_face_engine()
    suffix = ".mp4"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(video_bytes)
    tmp.flush()
    tmp_path = tmp.name

    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.sample_fps = sample_fps
    db.commit()

    timeline: list[dict] = []
    total_faces = 0
    max_faces = 0
    persisted = 0

    try:
        cap = _open_video(tmp_path)
        try:
            src_fps = cap.get(5) or 25.0  # CAP_PROP_FPS
            frame_count = int(cap.get(7) or 0)  # CAP_PROP_FRAME_COUNT
            duration = frame_count / src_fps if src_fps else 0.0
            step = max(1, int(round(src_fps / max(0.05, sample_fps))))
            expected_samples = max(1, frame_count // step) if frame_count else 0

            job.frames_total = expected_samples
            job.duration_seconds = round(duration, 2)
            db.commit()

            index = 0
            processed = 0
            while True:
                ok = cap.grab()
                if not ok:
                    break
                if index % step == 0:
                    ok, frame = cap.retrieve()
                    if ok and frame is not None:
                        rgb = frame[:, :, ::-1]
                        faces = engine.detect(np.ascontiguousarray(rgb), want_embeddings=False)
                        count = len(faces)
                        total_faces += count
                        max_faces = max(max_faces, count)
                        ts_ms = int((index / src_fps) * 1000) if src_fps else 0
                        timeline.append({"timestamp_ms": ts_ms, "face_count": count})

                        if persisted < max_persisted_detections:
                            for face in faces:
                                db.add(
                                    FaceDetection(
                                        tenant_id=job.tenant_id,
                                        media_id=media.id,
                                        frame_index=index,
                                        timestamp_ms=ts_ms,
                                        bbox_x1=face.bbox[0], bbox_y1=face.bbox[1],
                                        bbox_x2=face.bbox[2], bbox_y2=face.bbox[3],
                                        detection_confidence=round(face.confidence, 4),
                                        landmarks_json=json.dumps(face.landmarks),
                                        quality_json="{}",
                                    )
                                )
                                persisted += 1
                        processed += 1
                        job.frames_processed = processed
                        job.faces_detected = total_faces
                        job.max_faces_in_frame = max_faces
                        job.progress = round(min(100.0, (processed / expected_samples) * 100.0), 2) if expected_samples else 0.0
                        db.commit()
                        if progress_hook:
                            progress_hook(processed, expected_samples, total_faces)
                index += 1
        finally:
            cap.release()
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("Video job %s failed: %s", job.id, exc)
        raise
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    media.face_count = total_faces
    media.status = "completed"
    job.status = "completed"
    job.progress = 100.0
    job.finished_at = datetime.now(timezone.utc)
    job.faces_detected = total_faces
    job.max_faces_in_frame = max_faces
    db.commit()

    counts = [p["face_count"] for p in timeline] or [0]
    report = {
        "job_id": job.id,
        "media_id": media.id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": job.duration_seconds,
        "sample_fps": sample_fps,
        "frames_processed": job.frames_processed,
        "total_faces_detected": total_faces,
        "max_faces_in_frame": max_faces,
        "avg_faces_per_frame": round(sum(counts) / len(counts), 3),
        "timeline": timeline,
        "notices": [
            "Detection-only: no identities are inferred from video.",
            "Timeline reports anonymous face counts per sampled frame.",
        ],
    }
    return report


def estimate_sample_count(video_bytes: bytes, sample_fps: float) -> tuple[int, float]:
    """Best-effort quick estimate of frames to process and duration."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(video_bytes)
    tmp.flush()
    try:
        cap = _open_video(tmp.name)
        try:
            src_fps = cap.get(5) or 25.0
            frame_count = int(cap.get(7) or 0)
            duration = frame_count / src_fps if src_fps else 0.0
            step = max(1, int(round(src_fps / max(0.05, sample_fps))))
            return (max(1, frame_count // step) if frame_count else 0, duration)
        finally:
            cap.release()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def run_synchronously(db: Session, job: VideoJob, media: MediaAsset, video_bytes: bytes) -> dict:
    """Run processing inline (used when Celery is unavailable)."""
    start = time.perf_counter()
    report = process_video(db, job=job, media=media, video_bytes=video_bytes, sample_fps=job.sample_fps)
    logger.info("Video job %s processed synchronously in %.1fs", job.id, time.perf_counter() - start)
    return report
