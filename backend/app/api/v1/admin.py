"""Admin endpoints: users, roles, audit, retention, model status, video jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.security import Role, hash_password
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.media import MediaAsset, VideoJob
from app.models.retention import RetentionPolicy
from app.models.user import User
from app.schemas.admin import (
    AuditLogRead,
    ModelStatus,
    RetentionPolicyCreate,
    RetentionPolicyRead,
    SystemMetrics,
    UserAdminCreate,
    UserAdminRead,
    UserAdminUpdate,
)
from app.schemas.common import Page
from app.schemas.media import MediaRead, VideoJobRead
from app.services import retention as retention_service
from app.services.audit import record as audit_record
from app.services.face_engine import get_face_engine
from app.api.v1.health import _metrics

router = APIRouter()


# ---- Users & roles ---------------------------------------------------------
@router.get("/users", response_model=list[UserAdminRead], summary="List users in tenant")
def list_users(user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)) -> list[User]:
    return list(
        db.execute(select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at)).scalars().all()
    )


@router.post("/users", response_model=UserAdminRead, status_code=201, summary="Create user")
def create_user(
    payload: UserAdminCreate,
    request: Request,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    exists = db.execute(
        select(User).where(User.tenant_id == admin.tenant_id, User.email == payload.email.lower())
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="A user with that email already exists.")
    new_user = User(
        tenant_id=admin.tenant_id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    audit_record(
        db, tenant_id=admin.tenant_id, action="admin.user.create", actor_user_id=admin.id,
        actor_email=admin.email, resource_type="user", resource_id=new_user.id,
        detail={"role": payload.role}, request=request,
    )
    return new_user


@router.patch("/users/{user_id}", response_model=UserAdminRead, summary="Update user / role")
def update_user(
    user_id: str,
    payload: UserAdminUpdate,
    request: Request,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    target = db.get(User, user_id)
    if target is None or target.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if payload.role is not None:
        target.role = payload.role
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.password:
        target.hashed_password = hash_password(payload.password)
    db.commit()
    audit_record(
        db, tenant_id=admin.tenant_id, action="admin.user.update", actor_user_id=admin.id,
        actor_email=admin.email, resource_type="user", resource_id=target.id,
        detail={"role": target.role, "active": target.is_active}, request=request,
    )
    return target


# ---- Audit trail -----------------------------------------------------------
@router.get("/audit", response_model=Page[AuditLogRead], summary="Audit trail (append-only)")
def list_audit(
    action: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    user: User = Depends(require_role(Role.AUDITOR)),
    db: Session = Depends(get_db),
) -> Page[AuditLogRead]:
    stmt = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    ).scalars().all()
    return Page[AuditLogRead](
        items=[AuditLogRead.model_validate(r) for r in rows], total=total, page=page, size=size
    )


# ---- Model status ----------------------------------------------------------
@router.get("/models", response_model=list[ModelStatus], summary="Model status")
def model_status(user: User = Depends(require_role(Role.AUDITOR))) -> list[ModelStatus]:
    engine = get_face_engine()
    info = engine.model_info()
    from app.core.config import settings

    return [
        ModelStatus(
            name=settings.face_detection_model, task="detection", provider=info["provider"],
            embedding_dim=settings.face_embedding_dim, loaded=info["loaded"], is_mock=info["is_mock"],
            path=settings.model_dir,
        ),
        ModelStatus(
            name=settings.face_recognition_model, task="recognition", provider=info["provider"],
            embedding_dim=settings.face_embedding_dim, loaded=info["loaded"], is_mock=info["is_mock"],
            path=settings.model_dir,
        ),
    ]


# ---- Metrics ---------------------------------------------------------------
@router.get("/metrics", response_model=SystemMetrics, summary="Tenant metrics")
def metrics(user: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)) -> SystemMetrics:
    return _metrics(db, user.tenant_id)


# ---- Video jobs ------------------------------------------------------------
@router.get("/video-jobs", response_model=list[VideoJobRead], summary="All video jobs (admin)")
def video_jobs(user: User = Depends(require_role(Role.AUDITOR)), db: Session = Depends(get_db)) -> list[VideoJob]:
    return list(
        db.execute(
            select(VideoJob).where(VideoJob.tenant_id == user.tenant_id).order_by(VideoJob.created_at.desc())
        ).scalars().all()
    )


# ---- Retention policies ----------------------------------------------------
@router.get("/retention", response_model=list[RetentionPolicyRead], summary="List retention policies")
def list_retention(
    user: User = Depends(require_role(Role.AUDITOR)), db: Session = Depends(get_db)
) -> list[RetentionPolicy]:
    return list(
        db.execute(select(RetentionPolicy).where(RetentionPolicy.tenant_id == user.tenant_id)).scalars().all()
    )


@router.post("/retention", response_model=RetentionPolicyRead, status_code=201, summary="Create retention policy")
def create_retention(
    payload: RetentionPolicyCreate,
    request: Request,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> RetentionPolicy:
    policy = RetentionPolicy(
        tenant_id=admin.tenant_id, name=payload.name, resource_type=payload.resource_type,
        retention_days=payload.retention_days, action=payload.action, is_default=payload.is_default,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    audit_record(
        db, tenant_id=admin.tenant_id, action="admin.retention.create", actor_user_id=admin.id,
        actor_email=admin.email, resource_type="retention_policy", resource_id=policy.id,
        detail=payload.model_dump(mode="json"), request=request,
    )
    return policy


@router.delete("/retention/{policy_id}", status_code=204, summary="Delete retention policy")
def delete_retention(
    policy_id: str,
    request: Request,
    admin: User = Depends(require_role(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    policy = db.get(RetentionPolicy, policy_id)
    if policy is None or policy.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    audit_record(
        db, tenant_id=admin.tenant_id, action="admin.retention.delete", actor_user_id=admin.id,
        actor_email=admin.email, resource_type="retention_policy", resource_id=policy_id, request=request,
    )


@router.post("/retention/run", summary="Run retention sweep now")
def run_retention(
    request: Request, admin: User = Depends(require_role(Role.ADMIN)), db: Session = Depends(get_db)
) -> dict:
    bio = retention_service.purge_biometrics(db)
    media = retention_service.purge_expired_media(db)
    audit_record(
        db, tenant_id=admin.tenant_id, action="admin.retention.run", actor_user_id=admin.id,
        actor_email=admin.email, detail={"biometrics": bio, "media": media}, request=request,
    )
    return {"biometrics": bio, "media": media}
