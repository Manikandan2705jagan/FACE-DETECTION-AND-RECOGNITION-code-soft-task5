"""Upload-validation tests."""
from __future__ import annotations


def test_reject_unsupported_type(client, operator_headers):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 422
    assert "unsupported" in resp.json()["detail"].lower()


def test_reject_empty_file(client, operator_headers):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert resp.status_code == 422


def test_reject_corrupt_image(client, operator_headers):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("bad.jpg", b"not-really-a-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 422


def test_reject_oversized_image(client, operator_headers):
    from app.core.config import settings

    oversized = b"\xff\xd8\xff" + b"0" * (settings.max_upload_mb * 1024 * 1024 + 10)
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("big.jpg", oversized, "image/jpeg")},
    )
    assert resp.status_code == 422
    assert "maximum size" in resp.json()["detail"].lower()


def test_reject_unsupported_video_type(client, operator_headers):
    resp = client.post(
        "/api/v1/videos",
        headers=operator_headers,
        files={"file": ("clip.gif", b"GIF89a...", "image/gif")},
    )
    assert resp.status_code == 422
