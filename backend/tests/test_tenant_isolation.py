"""Tenant-isolation tests: one tenant must never read another tenant's data."""
from __future__ import annotations

import pytest

from app.core.security import Role, hash_password
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture(scope="module")
def other_tenant_headers(client):
    db = SessionLocal()
    try:
        tenant_b = db.query(Tenant).filter(Tenant.slug == "tenant-b").first()
        if tenant_b is None:
            tenant_b = Tenant(name="Tenant B", slug="tenant-b")
            db.add(tenant_b)
            db.flush()
        user = db.query(User).filter(User.email == "b@jarvas.dev").first()
        if user is None:
            user = User(
                tenant_id=tenant_b.id, email="b@jarvas.dev", full_name="Tenant B Admin",
                hashed_password=hash_password("tenant-b-password"), role=Role.ADMIN.value,
            )
            db.add(user)
            db.commit()
    finally:
        db.close()
    token = client.post(
        "/api/v1/auth/token", json={"email": "b@jarvas.dev", "password": "tenant-b-password"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_cannot_read_other_tenant_identity(client, operator_headers, other_tenant_headers, created_identity):
    resp = client.get(
        f"/api/v1/gallery/identities/{created_identity['id']}", headers=other_tenant_headers
    )
    assert resp.status_code == 404


def test_identity_list_is_scoped(client, other_tenant_headers, created_identity):
    resp = client.get("/api/v1/gallery/identities", headers=other_tenant_headers)
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert created_identity["id"] not in ids


def test_cannot_recognize_other_tenant_gallery(client, operator_headers, other_tenant_headers,
                                               created_identity, synthetic_image_bytes):
    # Enroll in tenant A.
    client.post(
        f"/api/v1/gallery/identities/{created_identity['id']}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    # Tenant B recognizing the same image must not match tenant A's identity.
    resp = client.post(
        "/api/v1/images/recognize",
        headers=other_tenant_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200
    for r in resp.json().get("recognition") or []:
        assert r["identity_id"] != created_identity["id"]


def test_cannot_delete_other_tenant_identity(client, other_tenant_headers, created_identity):
    resp = client.delete(f"/api/v1/gallery/identities/{created_identity['id']}", headers=other_tenant_headers)
    assert resp.status_code == 404
