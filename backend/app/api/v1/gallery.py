"""Identity gallery: consent-gated enrollment, listing, export, deletion."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.core.security import Role
from app.db.session import get_db
from app.models.identity import ConsentRecord, Enrollment, Identity
from app.models.user import User
from app.schemas.common import Page
from app.schemas.identity import (
    ConsentRead,
    ConsentUpdate,
    EnrollmentRead,
    IdentityCreate,
    IdentityExport,
    IdentityRead,
    IdentityUpdate,
    QualityReport,
)
from app.services.audit import record as audit_record
from app.services.enrollment import (
    ConsentError,
    EnrollmentError,
    consent_evidence_hash,
    enroll_identity,
    purge_identity,
)
from app.services.uploads import UploadRejected, validate_image_upload

router = APIRouter()

PRIVACY_NOTICE = (
    "Enrollment requires explicit, purpose-bound consent and is deletable at any time. "
    "Only local, consented identities are ever searchable."
)


def _fp(identity, db, tenant_id: str) -> IdentityRead:
    consents = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == tenant_id, ConsentRecord.identity_id == identity.id
        )
    ).scalars().all()
    active = [c for c in consents if c.is_active()]
    count = db.execute(
        select(func.count()).select_from(Enrollment).where(
            Enrollment.tenant_id == tenant_id, Enrollment.identity_id == identity.id,
            Enrollment.status == "active",
        )
    ).scalar_one()
    primary = active[0] if active else (consents[-1] if consents else None)
    return IdentityRead(
        id=identity.id,
        full_name=identity.full_name,
        notes=identity.notes,
        created_at=identity.created_at,
        updated_at=identity.updated_at,
        deleted_at=identity.deleted_at,
        consent_active=bool(active),
        consent_expires_at=primary.expires_at if primary else None,
        retention_until=primary.retention_until if primary else None,
        enrollment_count=int(count),
    )


@router.get("/notices", summary="Privacy notices shown throughout the UI")
def notices() -> dict:
    return {
        "enrollment": (
            "Biometric enrollment is voluntary. By proceeding you confirm the person gave explicit, "
            "informed consent for the stated purpose and retention period. Consent can be withdrawn "
            "and data permanently deleted at any time."
        ),
        "recognition": (
            "Recognition returns similarity-based CANDIDATES from the local consented gallery only. "
            "It is never certain and must be reviewed by a human before any action is taken."
        ),
        "general": PRIVACY_NOTICE,
    }


@router.post("/identities", response_model=IdentityRead, status_code=201, summary="Create identity + consent")
def create_identity(
    payload: IdentityCreate,
    request: Request,
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> IdentityRead:
    now = datetime.now(timezone.utc)
    if _aware(payload.consent.expires_at) <= now:
        raise HTTPException(status_code=422, detail="Consent expiry must be in the future.")
    if _aware(payload.consent.retention_until) <= now:
        raise HTTPException(status_code=422, detail="Retention date must be in the future.")

    identity = Identity(
        tenant_id=user.tenant_id, full_name=payload.full_name.strip(),
        notes=payload.notes or "", created_by=user.id,
    )
    db.add(identity)
    db.flush()

    evidence = consent_evidence_hash(
        identity.full_name, payload.consent.purpose, payload.consent.expires_at, payload.consent.retention_until
    )
    consent = ConsentRecord(
        tenant_id=user.tenant_id,
        identity_id=identity.id,
        purpose=payload.consent.purpose,
        granted_by=user.id,
        expires_at=payload.consent.expires_at,
        retention_until=payload.consent.retention_until,
        consent_text_version=payload.consent.consent_text_version,
        evidence_hash=evidence,
    )
    db.add(consent)
    db.commit()
    db.refresh(identity)

    audit_record(
        db, tenant_id=user.tenant_id, action="identity.create", actor_user_id=user.id,
        actor_email=user.email, resource_type="identity", resource_id=identity.id,
        detail={"consent": True, "purpose": payload.consent.purpose, "evidence_hash": evidence},
        request=request,
    )
    return _fp(identity, db, user.tenant_id)


@router.get("/identities", response_model=Page[IdentityRead], summary="List / search identities")
def list_identities(
    q: str | None = Query(default=None, description="Substring search on name"),
    consent_status: str | None = Query(default=None, pattern="^(active|expired|revoked|none)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[IdentityRead]:
    stmt = select(Identity).where(Identity.tenant_id == user.tenant_id, Identity.deleted_at.is_(None))
    if q:
        stmt = stmt.where(func.lower(Identity.full_name).like(f"%{q.lower()}%"))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    identities = db.execute(
        stmt.order_by(Identity.created_at.desc()).offset((page - 1) * size).limit(size)
    ).scalars().all()

    items = [_fp(i, db, user.tenant_id) for i in identities]
    if consent_status:
        def _match(item: IdentityRead) -> bool:
            if consent_status == "active":
                return item.consent_active
            if consent_status == "none":
                return item.consent_expires_at is None
            return not item.consent_active

        items = [i for i in items if _match(i)]

    return Page[IdentityRead](items=items, total=total, page=page, size=size)


def _get_identity(db: Session, tenant_id: str, identity_id: str) -> Identity:
    identity = db.get(Identity, identity_id)
    if identity is None or identity.tenant_id != tenant_id or identity.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    return identity


@router.get("/identities/{identity_id}", response_model=IdentityRead, summary="Identity detail")
def get_identity(identity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> IdentityRead:
    identity = _get_identity(db, user.tenant_id, identity_id)
    return _fp(identity, db, user.tenant_id)


@router.patch("/identities/{identity_id}", response_model=IdentityRead, summary="Update identity metadata")
def update_identity(
    identity_id: str,
    payload: IdentityUpdate,
    request: Request,
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> IdentityRead:
    identity = _get_identity(db, user.tenant_id, identity_id)
    if payload.full_name is not None:
        identity.full_name = payload.full_name.strip()
    if payload.notes is not None:
        identity.notes = payload.notes
    db.commit()
    audit_record(
        db, tenant_id=user.tenant_id, action="identity.update", actor_user_id=user.id,
        actor_email=user.email, resource_type="identity", resource_id=identity_id, request=request,
    )
    return _fp(identity, db, user.tenant_id)


@router.patch("/identities/{identity_id}/consent", response_model=IdentityRead, summary="Update / revoke consent")
def update_consent(
    identity_id: str,
    payload: ConsentUpdate,
    request: Request,
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> IdentityRead:
    identity = _get_identity(db, user.tenant_id, identity_id)
    consent = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == user.tenant_id,
            ConsentRecord.identity_id == identity_id,
            ConsentRecord.revoked_at.is_(None),
        )
    ).scalars().first()
    if consent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active consent to update")

    if payload.expires_at is not None:
        consent.expires_at = payload.expires_at
    if payload.retention_until is not None:
        consent.retention_until = payload.retention_until
    if payload.purpose is not None:
        consent.purpose = payload.purpose
    if payload.revoked:
        consent.revoked_at = datetime.now(timezone.utc)
        # Revoking consent disables all templates immediately.
        for e in identity.enrollments:
            e.status = "revoked"
    db.commit()
    audit_record(
        db, tenant_id=user.tenant_id, action="consent.update" if not payload.revoked else "consent.revoke",
        actor_user_id=user.id, actor_email=user.email, resource_type="identity", resource_id=identity_id,
        detail={"revoked": bool(payload.revoked)}, request=request,
    )
    return _fp(identity, db, user.tenant_id)


@router.post(
    "/identities/{identity_id}/enroll",
    response_model=EnrollmentRead,
    status_code=201,
    summary="Enroll a face (requires consent + exactly one clear face)",
)
def enroll(
    identity_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> Enrollment:
    identity = _get_identity(db, user.tenant_id, identity_id)
    raw = file.file.read()
    try:
        validated = validate_image_upload(raw, file.content_type or "application/octet-stream")
    except UploadRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message)

    try:
        enrollment = enroll_identity(
            db, tenant_id=user.tenant_id, identity=identity, image_rgb=validated.image, user_id=user.id,
        )
    except ConsentError as exc:
        audit_record(
            db, tenant_id=user.tenant_id, action="identity.enroll.rejected", actor_user_id=user.id,
            actor_email=user.email, outcome="denied", resource_type="identity", resource_id=identity_id,
            detail={"reason": str(exc)}, request=request,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except EnrollmentError as exc:
        audit_record(
            db, tenant_id=user.tenant_id, action="identity.enroll.rejected", actor_user_id=user.id,
            actor_email=user.email, outcome="rejected", resource_type="identity", resource_id=identity_id,
            detail={"reason": exc.message, "reasons": exc.reasons}, request=request,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.message, "reasons": exc.reasons},
        )

    db.commit()
    db.refresh(enrollment)
    audit_record(
        db, tenant_id=user.tenant_id, action="identity.enroll", actor_user_id=user.id,
        actor_email=user.email, resource_type="enrollment", resource_id=enrollment.id,
        detail={"identity_id": identity_id, "quality_score": enrollment.quality_score}, request=request,
    )
    return enrollment


@router.get("/identities/{identity_id}/export", response_model=IdentityExport, summary="Export identity data")
def export_identity(
    identity_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> IdentityExport:
    identity = _get_identity(db, user.tenant_id, identity_id)
    consents = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == user.tenant_id, ConsentRecord.identity_id == identity_id
        )
    ).scalars().all()
    enrollments = db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == user.tenant_id, Enrollment.identity_id == identity_id
        )
    ).scalars().all()
    return IdentityExport(
        identity=_fp(identity, db, user.tenant_id),
        consents=[ConsentRead.model_validate(c) for c in consents],
        enrollments=[EnrollmentRead.model_validate(e) for e in enrollments],
        exported_at=datetime.now(timezone.utc),
    )


@router.delete("/identities/{identity_id}", status_code=204, summary="Permanently delete identity")
def delete_identity(
    identity_id: str,
    request: Request,
    user: User = Depends(require_role(Role.OPERATOR)),
    db: Session = Depends(get_db),
) -> None:
    identity = _get_identity(db, user.tenant_id, identity_id)
    name = identity.full_name
    audit_record(
        db, tenant_id=user.tenant_id, action="identity.delete", actor_user_id=user.id,
        actor_email=user.email, resource_type="identity", resource_id=identity_id,
        detail={"identity": name, "irreversible": True}, request=request,
    )
    purge_identity(db, user.tenant_id, identity)
    db.commit()


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
