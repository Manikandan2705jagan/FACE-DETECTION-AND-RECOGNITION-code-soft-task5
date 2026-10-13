"""Consent-enforcement tests — the core privacy invariant."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.identity import Identity


def test_consent_checkbox_must_be_true(client, operator_headers, consent_payload):
    bad = dict(consent_payload)
    bad["consent_granted"] = False
    resp = client.post(
        "/api/v1/gallery/identities",
        headers=operator_headers,
        json={"full_name": "No Consent", "notes": "", "consent": bad},
    )
    assert resp.status_code == 422


def test_enrollment_without_consent_is_denied(client, operator_headers, synthetic_image_bytes, consent_payload):
    tenant = _tenant_id()
    db = SessionLocal()
    try:
        identity = Identity(tenant_id=tenant, full_name="No Consent Subject", notes="")
        db.add(identity)
        db.commit()
        identity_id = identity.id
    finally:
        db.close()

    resp = client.post(
        f"/api/v1/gallery/identities/{identity_id}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 403


def test_enrollment_with_consent_succeeds(client, operator_headers, created_identity, synthetic_image_bytes):
    resp = client.post(
        f"/api/v1/gallery/identities/{created_identity['id']}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "active"


def test_enrollment_rejects_image_without_face(client, operator_headers, created_identity, blank_image_bytes):
    resp = client.post(
        f"/api/v1/gallery/identities/{created_identity['id']}/enroll",
        headers=operator_headers,
        files={"file": ("blank.jpg", blank_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "face" in str(detail).lower()


def test_consent_must_be_future(client, operator_headers, consent_payload):
    bad = dict(consent_payload)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    bad["expires_at"] = past.isoformat()
    resp = client.post(
        "/api/v1/gallery/identities",
        headers=operator_headers,
        json={"full_name": "Past Consent", "notes": "", "consent": bad},
    )
    assert resp.status_code == 422


def _tenant_id() -> str:
    from app.models.tenant import Tenant

    db = SessionLocal()
    try:
        return db.query(Tenant).first().id
    finally:
        db.close()
