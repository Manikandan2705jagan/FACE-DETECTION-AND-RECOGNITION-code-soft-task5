"""Role-based access control tests."""
from __future__ import annotations


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/v1/gallery/identities").status_code == 401
    assert client.get("/api/v1/admin/users").status_code == 401


def test_viewer_cannot_create_identity(client, viewer_headers, consent_payload):
    resp = client.post(
        "/api/v1/gallery/identities",
        headers=viewer_headers,
        json={"full_name": "Should Fail", "notes": "", "consent": consent_payload},
    )
    assert resp.status_code == 403


def test_operator_can_create_identity(client, operator_headers, consent_payload):
    resp = client.post(
        "/api/v1/gallery/identities",
        headers=operator_headers,
        json={"full_name": "Operator Created", "notes": "", "consent": consent_payload},
    )
    assert resp.status_code == 201


def test_viewer_cannot_list_users(client, viewer_headers):
    assert client.get("/api/v1/admin/users", headers=viewer_headers).status_code == 403


def test_operator_cannot_list_users(client, operator_headers):
    assert client.get("/api/v1/admin/users", headers=operator_headers).status_code == 403


def test_admin_can_list_users(client, admin_headers):
    resp = client.get("/api/v1/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_auditor_can_read_audit_but_not_manage_users(client, auditor_headers):
    assert client.get("/api/v1/admin/audit", headers=auditor_headers).status_code == 200
    resp = client.post(
        "/api/v1/admin/users",
        headers=auditor_headers,
        json={"email": "nope@jarvas.local", "password": "password123", "role": "viewer"},
    )
    assert resp.status_code == 403


def test_viewer_cannot_recognize(client, viewer_headers, synthetic_image_bytes):
    resp = client.post(
        "/api/v1/images/recognize",
        headers=viewer_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 403
