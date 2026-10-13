"""Retention enforcement and irreversible deletion.

Invoked by a scheduled job (Celery beat / cron). Deletions are hard deletes and
are logged to the audit trail; object storage blobs are removed too.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.identity import ConsentRecord, Enrollment, Identity
from app.models.media import MediaAsset
from app.services.audit import record as audit_record
from app.services.storage import get_storage

logger = get_logger(__name__)


def purge_biometrics(db: Session) -> dict:
    """Delete embeddings whose consent retention window has elapsed."""
    now = datetime.now(timezone.utc)
    consents = db.execute(select(ConsentRecord)).scalars().all()
    expired_ids = []
    for c in consents:
        ref = c.retention_until
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=now.tzinfo)
        if ref < now:
            expired_ids.append(c.id)
    if not expired_ids:
        return {"enrollments_deleted": 0, "identities_purged": 0}

    enrollments = db.execute(
        select(Enrollment).where(Enrollment.consent_record_id.in_(expired_ids))
    ).scalars().all()
    deleted = 0
    tenant_ids = set()
    for e in enrollments:
        tenant_ids.add(e.tenant_id)
        db.delete(e)
        deleted += 1

    # Purge identities whose only consents have fully elapsed.
    identities_purged = 0
    for identity in db.execute(select(Identity)).scalars().all():
        recs = [c for c in identity.consent_records]
        if not recs:
            continue
        if any(c.is_active(now) for c in recs):
            continue
        all_elapsed = all(
            (c.retention_until.replace(tzinfo=now.tzinfo) if c.retention_until.tzinfo is None else c.retention_until) < now
            for c in recs
        )
        if all_elapsed:
            tenant_ids.add(identity.tenant_id)
            db.delete(identity)
            identities_purged += 1

    db.commit()
    for tid in tenant_ids:
        audit_record(
            db, tenant_id=tid, action="retention.purge_biometrics", resource_type="identity",
            detail={"enrollments_deleted": deleted, "identities_purged": identities_purged},
        )
    return {"enrollments_deleted": deleted, "identities_purged": identities_purged}


def purge_expired_media(db: Session) -> dict:
    """Delete media assets past the configured retention window."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    cutoff = now - timedelta(days=settings.default_retention_days)
    storage = get_storage()
    removed = 0
    assets = db.execute(select(MediaAsset)).scalars().all()
    for asset in assets:
        created = asset.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=now.tzinfo)
        if created < cutoff:
            prefix = f"results/{asset.tenant_id}/{asset.id}"
            storage.delete_prefix(prefix)
            if asset.storage_key:
                storage.delete(asset.storage_key)
            audit_record(
                db, tenant_id=asset.tenant_id, action="retention.purge_media",
                resource_type="media", resource_id=asset.id, commit=False,
            )
            db.delete(asset)
            removed += 1
    db.commit()
    return {"media_deleted": removed}
