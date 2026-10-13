"""Consent-gated gallery search.

Only enrollments that (a) are active, (b) belong to a non-deleted identity and
(c) have a currently-valid, non-revoked consent record are ever considered. The
search is brute-force cosine over decrypted embeddings, which keeps biometric
templates encrypted at rest. (pgvector can be enabled for large galleries — see
docs/ARCHITECTURE.md; it is disabled by default precisely so plaintext templates
are never persisted.)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.identity import ConsentRecord, Enrollment, Identity
from app.services.crypto import decrypt_embedding
from app.services.face_engine import cosine_similarity


@dataclass
class Candidate:
    identity_id: str
    name: str
    cosine_similarity: float
    threshold: float
    manual_review_required: bool
    status: str


def _active_consent_map(db: Session, tenant_id: str, identity_ids: list[str]) -> dict[str, ConsentRecord]:
    if not identity_ids:
        return {}
    rows = db.execute(
        select(ConsentRecord).where(
            ConsentRecord.tenant_id == tenant_id,
            ConsentRecord.identity_id.in_(identity_ids),
            ConsentRecord.revoked_at.is_(None),
        )
    ).scalars().all()
    now = (
        datetime.now(tz=rows[0].expires_at.tzinfo)
        if rows and rows[0].expires_at.tzinfo
        else datetime.now(timezone.utc)
    )
    active: dict[str, ConsentRecord] = {}
    for rec in rows:
        if rec.is_active(now):
            active[rec.identity_id] = rec
    return active


def active_enrollments(db: Session, tenant_id: str) -> list[tuple[Identity, Enrollment]]:
    """Return (identity, enrollment) pairs eligible for recognition."""
    enrollments = db.execute(
        select(Enrollment).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.status == "active",
        )
    ).scalars().all()
    if not enrollments:
        return []
    identity_ids = list({e.identity_id for e in enrollments})
    identities = {
        i.id: i
        for i in db.execute(
            select(Identity).where(
                Identity.tenant_id == tenant_id,
                Identity.id.in_(identity_ids),
                Identity.deleted_at.is_(None),
            )
        ).scalars().all()
    }
    active_consents = _active_consent_map(db, tenant_id, list(identities.keys()))
    pairs: list[tuple[Identity, Enrollment]] = []
    for e in enrollments:
        ident = identities.get(e.identity_id)
        if ident is None:
            continue
        if e.identity_id not in active_consents:
            continue  # no valid consent -> not searchable
        pairs.append((ident, e))
    return pairs


def search(
    db: Session,
    tenant_id: str,
    query_embedding,
    threshold: float | None = None,
    top_k: int = 3,
) -> list[Candidate]:
    threshold = settings.default_similarity_threshold if threshold is None else threshold
    scored: list[Candidate] = []
    for ident, enrollment in active_enrollments(db, tenant_id):
        try:
            emb = decrypt_embedding(enrollment.embedding_encrypted, enrollment.embedding_dim)
        except Exception:
            continue
        sim = cosine_similarity(query_embedding, emb)
        status = "candidate" if sim >= threshold else "no_match"
        scored.append(
            Candidate(
                identity_id=ident.id,
                name=ident.full_name,
                cosine_similarity=round(sim, 4),
                threshold=threshold,
                # A match is NEVER certain: human review is always required.
                manual_review_required=True,
                status=status,
            )
        )
    scored.sort(key=lambda c: c.cosine_similarity, reverse=True)
    best = scored[:top_k]
    # If the best score is below threshold, report a single no_match entry with
    # NO identity attached (a below-threshold score must not leak a candidate).
    if not best or best[0].cosine_similarity < threshold:
        if best:
            best = [
                Candidate(
                    identity_id="",
                    name="",
                    cosine_similarity=best[0].cosine_similarity,
                    threshold=threshold,
                    manual_review_required=True,
                    status="no_match",
                )
            ]
        else:
            best = [
                Candidate(
                    identity_id="",
                    name="",
                    cosine_similarity=0.0,
                    threshold=threshold,
                    manual_review_required=True,
                    status="no_match",
                )
            ]
    return best


def gallery_size(db: Session, tenant_id: str) -> int:
    return len(active_enrollments(db, tenant_id))
