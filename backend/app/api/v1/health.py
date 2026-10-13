"""Health / readiness / model-status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.core.deps import get_current_user, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models.identity import ConsentRecord, Enrollment, Identity
from app.models.media import MediaAsset, VideoJob
from app.models.user import User
from app.schemas.admin import (
    HealthComponent,
    HealthStatus,
    ModelStatus,
    SystemMetrics,
)
from app.services.face_engine import get_face_engine

router = APIRouter()


def _db_component(db: Session) -> HealthComponent:
    try:
        db.execute(text("SELECT 1"))
        return HealthComponent(name="database", status="ok", detail="reachable")
    except Exception as exc:  # pragma: no cover
        return HealthComponent(name="database", status="down", detail=str(exc)[:200])


def _redis_component() -> HealthComponent:
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=1.5)
        client.ping()
        return HealthComponent(name="redis", status="ok", detail="reachable")
    except Exception as exc:  # pragma: no cover
        return HealthComponent(name="redis", status="degraded", detail=f"unavailable: {str(exc)[:160]}")


def _storage_component() -> HealthComponent:
    try:
        from app.services.storage import LocalStorage, get_storage

        storage = get_storage()
        backend = "local" if isinstance(storage, LocalStorage) else "s3"
        return HealthComponent(name="storage", status="ok", detail=backend)
    except Exception as exc:  # pragma: no cover
        return HealthComponent(name="storage", status="down", detail=str(exc)[:160])


def _model_statuses() -> list[ModelStatus]:
    engine = get_face_engine()
    info = engine.model_info()
    return [
        ModelStatus(
            name=settings.face_detection_model,
            task="detection",
            provider=info["provider"],
            embedding_dim=settings.face_embedding_dim,
            loaded=info["loaded"],
            is_mock=info["is_mock"],
            path=settings.model_dir,
        ),
        ModelStatus(
            name=settings.face_recognition_model,
            task="recognition",
            provider=info["provider"],
            embedding_dim=settings.face_embedding_dim,
            loaded=info["loaded"],
            is_mock=info["is_mock"],
            path=settings.model_dir,
        ),
    ]


@router.get("/live", summary="Liveness probe")
def live() -> dict:
    return {"status": "ok", "version": __version__}


@router.get("/ready", summary="Readiness probe")
def ready(db: Session = Depends(get_db)) -> dict:
    comp = _db_component(db)
    return {"status": "ok" if comp.status == "ok" else "degraded", "database": comp.status}


@router.get("", response_model=HealthStatus, summary="Full health + model status")
def health(db: Session = Depends(get_db)) -> HealthStatus:
    components = [_db_component(db), _redis_component(), _storage_component()]
    overall = "ok" if all(c.status == "ok" for c in components) else "degraded"
    return HealthStatus(
        status=overall,
        version=__version__,
        env=settings.env,
        components=components,
        models=_model_statuses(),
    )


@router.get("/metrics", response_model=HealthStatus, summary="Health + system metrics (admin)")
def health_metrics(
    user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> HealthStatus:
    status = health(db)  # type: ignore[arg-type]
    status.metrics = _metrics(db, user.tenant_id)
    return status


def _metrics(db: Session, tenant_id: str) -> SystemMetrics:
    from datetime import datetime, timezone

    consents = db.execute(
        select(ConsentRecord).where(ConsentRecord.tenant_id == tenant_id)
    ).scalars().all()
    now = datetime.now(timezone.utc)
    active = sum(1 for c in consents if c.is_active(now))
    return SystemMetrics(
        total_identities=db.execute(
            select(func.count()).select_from(Identity).where(
                Identity.tenant_id == tenant_id, Identity.deleted_at.is_(None)
            )
        ).scalar_one(),
        active_consents=active,
        expired_consents=len(consents) - active,
        total_media=db.execute(
            select(func.count()).select_from(MediaAsset).where(MediaAsset.tenant_id == tenant_id)
        ).scalar_one(),
        total_video_jobs=db.execute(
            select(func.count()).select_from(VideoJob).where(VideoJob.tenant_id == tenant_id)
        ).scalar_one(),
        pending_video_jobs=db.execute(
            select(func.count()).select_from(VideoJob).where(
                VideoJob.tenant_id == tenant_id, VideoJob.status.in_(["queued", "running"])
            )
        ).scalar_one(),
    )


__all__ = ["router", "_metrics"]
