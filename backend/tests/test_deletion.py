"""Irreversible deletion tests."""
from __future__ import annotations


def test_delete_identity_purges_enrollments(client, operator_headers, created_identity, synthetic_image_bytes):
    identity_id = created_identity["id"]
    enroll = client.post(
        f"/api/v1/gallery/identities/{identity_id}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert enroll.status_code == 201

    resp = client.delete(f"/api/v1/gallery/identities/{identity_id}", headers=operator_headers)
    assert resp.status_code == 204

    assert client.get(f"/api/v1/gallery/identities/{identity_id}", headers=operator_headers).status_code == 404


def test_deleted_identity_is_not_searchable(client, operator_headers, created_identity, synthetic_image_bytes):
    identity_id = created_identity["id"]
    client.post(
        f"/api/v1/gallery/identities/{identity_id}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    client.delete(f"/api/v1/gallery/identities/{identity_id}", headers=operator_headers)

    resp = client.post(
        "/api/v1/images/recognize",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200
    # The purged identity must not appear as a candidate.
    for r in resp.json().get("recognition") or []:
        assert r["identity_id"] != identity_id


def test_delete_is_audited(client, admin_headers, operator_headers, created_identity):
    identity_id = created_identity["id"]
    client.delete(f"/api/v1/gallery/identities/{identity_id}", headers=operator_headers)
    audit = client.get("/api/v1/admin/audit", headers=admin_headers, params={"action": "identity.delete"})
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1
