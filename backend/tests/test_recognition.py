"""Recognition tests — candidates only, never certain, consent-gated."""
from __future__ import annotations

import io

from app.seed import synthetic_face


def _jpeg(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def test_recognition_returns_candidate_requiring_review(client, operator_headers, created_identity):
    identity_id = created_identity["id"]
    # Use an image unique to this identity so the gallery match is unambiguous.
    unique = _jpeg(synthetic_face(seed=abs(hash(identity_id)) % 100000))
    enroll = client.post(
        f"/api/v1/gallery/identities/{identity_id}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", unique, "image/jpeg")},
    )
    assert enroll.status_code == 201, enroll.text

    resp = client.post(
        "/api/v1/images/recognize",
        headers=operator_headers,
        files={"file": ("face.jpg", unique, "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "recognition"
    assert body["recognition"], "expected at least one candidate entry"

    top = body["recognition"][0]
    assert top["candidate_name"] == created_identity["full_name"]
    assert top["status"] == "candidate"
    assert top["manual_review_required"] is True
    assert 0.0 <= top["cosine_similarity"] <= 1.0
    assert top["threshold"] > 0
    # Never assert certainty.
    assert top["status"] not in {"match", "confirmed", "certain"}
    assert any("review" in n.lower() for n in body["notices"])


def test_unknown_face_yields_no_match(client, operator_headers, created_identity):
    client.post(
        f"/api/v1/gallery/identities/{created_identity['id']}/enroll",
        headers=operator_headers,
        files={"file": ("face.jpg", _jpeg(synthetic_face(seed=555)), "image/jpeg")},
    )
    resp = client.post(
        "/api/v1/images/recognize",
        headers=operator_headers,
        files={"file": ("unknown.jpg", _jpeg(synthetic_face(seed=99999)), "image/jpeg")},
    )
    assert resp.status_code == 200
    for r in resp.json()["recognition"]:
        assert r["status"] in {"no_match", "candidate"}
        if r["status"] == "no_match":
            assert r["identity_id"] in (None, "")
