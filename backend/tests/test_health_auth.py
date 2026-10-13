"""Health + auth endpoint tests."""
from __future__ import annotations

import os


def test_liveness(client):
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readiness(client):
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200
    assert resp.json()["database"] == "ok"


def test_full_health_has_models(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert any(m["task"] == "detection" for m in body["models"])


def test_login_success(client):
    resp = client.post(
        "/api/v1/auth/token",
        json={"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password(client):
    resp = client.post(
        "/api/v1/auth/token",
        json={"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": "wrong-password"},
    )
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_user(client, admin_headers):
    resp = client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
