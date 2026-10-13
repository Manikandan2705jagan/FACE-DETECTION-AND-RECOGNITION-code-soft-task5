"""Detection-only endpoint tests."""
from __future__ import annotations


def test_detection_returns_faces_and_metadata(client, operator_headers, synthetic_image_bytes):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "detection"
    assert body["face_count"] >= 1
    assert body["processing_ms"] >= 0
    det = body["detections"][0]
    assert set(det["bbox"].keys()) == {"x1", "y1", "x2", "y2"}
    assert 0.0 <= det["confidence"] <= 1.0
    assert det["landmarks"]
    # Detection-only must not return identity information.
    assert body.get("recognition") in (None, [])


def test_annotated_download(client, operator_headers, synthetic_image_bytes):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    media_id = resp.json()["media_id"]
    out = client.get(f"/api/v1/images/{media_id}/annotated", headers=operator_headers)
    assert out.status_code == 200
    assert out.headers["content-type"] == "image/jpeg"
    assert len(out.content) > 0


def test_detections_json(client, operator_headers, synthetic_image_bytes):
    resp = client.post(
        "/api/v1/images/detect",
        headers=operator_headers,
        files={"file": ("face.jpg", synthetic_image_bytes, "image/jpeg")},
    )
    media_id = resp.json()["media_id"]
    out = client.get(f"/api/v1/images/{media_id}/detections", headers=operator_headers)
    assert out.status_code == 200
    assert out.json()["face_count"] >= 1
