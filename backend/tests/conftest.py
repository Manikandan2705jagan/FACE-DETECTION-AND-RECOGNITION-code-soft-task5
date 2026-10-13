"""Pytest configuration and shared fixtures.

Environment is configured BEFORE importing the application so that
``settings`` picks up test-safe values (SQLite, local storage, mock engine).
"""
from __future__ import annotations

import io
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="jarvas-test-")
os.environ.update(
    {
        "JARVAS_ENV": "test",
        "JARVAS_LOG_LEVEL": "WARNING",
        "DATABASE_URL": f"sqlite+pysqlite:///{os.path.join(_TMP, 'test.sqlite3')}",
        "STORAGE_BACKEND": "local",
        "ALLOW_MOCK_FACE_ENGINE": "true",
        "RECOGNITION_ENABLED": "true",
        "JWT_SECRET": "test-secret-value-please-change-0123456789abcdef",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "BIOMETRIC_ENCRYPTION_KEY": "test-biometric-key",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@jarvas.dev",
        "BOOTSTRAP_ADMIN_PASSWORD": "admin-test-password",
        "DEFAULT_SIMILARITY_THRESHOLD": "0.38",
        "MIN_FACE_SIZE": "80",
        "MODEL_DIR": _TMP,
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import Role, hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.seed import synthetic_face  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def tenant_id() -> str:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).first()
        assert tenant is not None
        return tenant.id
    finally:
        db.close()


def _ensure_user(email: str, role: Role, password: str) -> str:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).first()
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                tenant_id=tenant.id, email=email, full_name=email.split("@")[0],
                hashed_password=hash_password(password), role=role.value,
            )
            db.add(user)
            db.commit()
        return user.id
    finally:
        db.close()


def _token(client, email: str, password: str) -> str:
    resp = client.post("/api/v1/auth/token", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(client) -> dict:
    token = _token(client, os.environ["BOOTSTRAP_ADMIN_EMAIL"], os.environ["BOOTSTRAP_ADMIN_PASSWORD"])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def operator_headers(client) -> dict:
    email, pwd = "operator@jarvas.dev", "operator-test-password"
    _ensure_user(email, Role.OPERATOR, pwd)
    return {"Authorization": f"Bearer {_token(client, email, pwd)}"}


@pytest.fixture(scope="session")
def viewer_headers(client) -> dict:
    email, pwd = "viewer@jarvas.dev", "viewer-test-password"
    _ensure_user(email, Role.VIEWER, pwd)
    return {"Authorization": f"Bearer {_token(client, email, pwd)}"}


@pytest.fixture(scope="session")
def auditor_headers(client) -> dict:
    email, pwd = "auditor@jarvas.dev", "auditor-test-password"
    _ensure_user(email, Role.AUDITOR, pwd)
    return {"Authorization": f"Bearer {_token(client, email, pwd)}"}


def _jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture()
def synthetic_image_bytes() -> bytes:
    return _jpeg(synthetic_face(seed=4242))


@pytest.fixture()
def blank_image_bytes() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (256, 256), (10, 10, 10))
    return _jpeg(img)


def _future_consent() -> dict:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    return {
        "consent_granted": True,
        "purpose": "Automated test enrollment",
        "expires_at": (now + timedelta(days=30)).isoformat(),
        "retention_until": (now + timedelta(days=60)).isoformat(),
        "consent_text_version": "2026-01",
    }


@pytest.fixture()
def consent_payload() -> dict:
    return _future_consent()


@pytest.fixture()
def created_identity(client, operator_headers, consent_payload):
    resp = client.post(
        "/api/v1/gallery/identities",
        headers=operator_headers,
        json={"full_name": "Test Subject One", "notes": "fixture", "consent": consent_payload},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()
