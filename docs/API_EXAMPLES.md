# API Examples

Base URL (local): `http://localhost:8000` — all endpoints are under `/api/v1`.
Interactive docs: `http://localhost:8000/docs`.

Roles: `viewer` < `auditor` < `operator` < `admin` (higher roles include lower-role access).

---

## Authentication

```bash
# 1. Obtain a JWT (JSON body)
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jarvas.dev","password":"change-me-admin-password"}'
# -> {"access_token":"...","token_type":"bearer","expires_in":3600,"role":"admin","tenant_id":"..."}

# Store it for the rest of the session
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@jarvas.dev","password":"change-me-admin-password"}' | jq -r .access_token)

# Current user (viewer+)
curl -s http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

Swagger's **Authorize** button uses the OAuth2 password flow at `POST /auth/token/form`.

---

## Image detection (viewer+) — no identity

```bash
curl -s -X POST http://localhost:8000/api/v1/images/detect \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg"
```

Response (abridged):

```json
{
  "media_id": "9f...",
  "kind": "image",
  "face_count": 1,
  "processing_ms": 42.1,
  "width": 1280,
  "height": 720,
  "mode": "detection",
  "detections": [
    {
      "id": "det-0",
      "bbox": {"x1": 410, "y1": 120, "x2": 610, "y2": 360},
      "confidence": 0.97,
      "landmarks": [[450, 200], [560, 200], [505, 250], [460, 300], [550, 300]],
      "quality": {"passed": true, "blur": 0.82, "lighting": 0.77, "pose": 0.91, "face_size_px": 240, "reasons": []}
    }
  ],
  "annotated_url": "/api/v1/images/9f.../annotated",
  "notices": ["This tool performs face DETECTION by default. ..."]
}
```

Other image endpoints:

```bash
curl -s http://localhost:8000/api/v1/images -H "Authorization: Bearer $TOKEN"                 # list uploads
curl -s http://localhost:8000/api/v1/images/$MEDIA_ID -H "Authorization: Bearer $TOKEN"       # detail
curl -s -o annotated.jpg http://localhost:8000/api/v1/images/$MEDIA_ID/annotated \
  -H "Authorization: Bearer $TOKEN"                                                           # download annotated
curl -s http://localhost:8000/api/v1/images/$MEDIA_ID/detections -H "Authorization: Bearer $TOKEN"
```

---

## Image recognition (operator+) — advisory candidates only

Searches **only** the local, consented gallery. `threshold` must be `0..1` (optional; defaults to
the server `DEFAULT_SIMILARITY_THRESHOLD`). Requires `RECOGNITION_ENABLED=true`.

```bash
curl -s -X POST http://localhost:8000/api/v1/images/recognize \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@probe.jpg" \
  -F "threshold=0.40" \
  -F "top_k=3"
```

```json
{
  "mode": "recognition",
  "detections": [ ... ],
  "recognition": [
    {
      "identity_id": "5c...",
      "candidate_name": "Alex Rivera",
      "cosine_similarity": 0.61,
      "threshold": 0.40,
      "manual_review_required": true,
      "status": "candidate"
    }
  ],
  "notices": ["Recognition returns similarity-based CANDIDATES ... human review required."]
}
```

Below threshold returns `{"cosine_similarity": ..., "status": "no_match"}` with **no identity**
attached. A match is never a confirmed identity.

---

## Video detection (viewer+) — face-count timeline

```bash
# Upload (processing runs in the background worker; inline fallback if the broker is down)
curl -s -X POST http://localhost:8000/api/v1/videos \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@clip.mp4" \
  -F "sample_fps=1" \
  -F "process_async=true"
# -> {"id":"<job>","status":"queued","frames_total":120,"duration_seconds":120.0,...}

# Poll status/progress
curl -s http://localhost:8000/api/v1/videos/$JOB_ID -H "Authorization: Bearer $TOKEN"

# Face-count timeline
curl -s http://localhost:8000/api/v1/videos/$JOB_ID/report -H "Authorization: Bearer $TOKEN"
# -> {"job":{...},"media":{...},"timeline":[{"timestamp_ms":0,"face_count":2}, ...],"notes":[...]}

# Download the JSON report
curl -s -o report.json http://localhost:8000/api/v1/videos/$JOB_ID/report.json \
  -H "Authorization: Bearer $TOKEN"

curl -s http://localhost:8000/api/v1/videos -H "Authorization: Bearer $TOKEN"   # list jobs
```

---

## Gallery (consented identities)

### Privacy notices (public)

```bash
curl -s http://localhost:8000/api/v1/gallery/notices
```

### Create an identity with explicit consent (operator+)

`consent.consent_granted` **must** be `true`; `expires_at` and `retention_until` must be in the
future (UTC ISO-8601).

```bash
curl -s -X POST http://localhost:8000/api/v1/gallery/identities \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "full_name": "Alex Rivera",
    "notes": "Voluntary building access enrollment",
    "consent": {
      "consent_granted": true,
      "purpose": "Voluntary access-control enrollment",
      "expires_at": "2027-01-01T12:00:00Z",
      "retention_until": "2026-07-01T12:00:00Z",
      "consent_text_version": "2026-01"
    }
  }'
# -> 201 {"id":"<identity>","consent_active":true,"enrollment_count":0, ...}
```

### Enroll a face (operator+) — requires exactly one clear face

```bash
curl -s -X POST http://localhost:8000/api/v1/gallery/identities/$IDENTITY_ID/enroll \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@enrollment.jpg"
# -> 201 {"id":"...","status":"active","quality_score":0.83,"model_name":"..."}
```

Rejections:
- `403` — no active consent (`ConsentError`).
- `422` — quality failure: `{"detail":{"message":"...","reasons":["Exactly one face required", ...]}}`.

### List / search identities (viewer+)

```bash
curl -s "http://localhost:8000/api/v1/gallery/identities?q=alex&consent_status=active&page=1&size=20" \
  -H "Authorization: Bearer $TOKEN"
# consent_status: active | expired | revoked | none
```

### Update or revoke consent (operator+)

```bash
# Extend expiry / retention
curl -s -X PATCH http://localhost:8000/api/v1/gallery/identities/$IDENTITY_ID/consent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"expires_at":"2027-06-01T12:00:00Z","retention_until":"2026-12-01T12:00:00Z"}'

# Revoke (templates immediately excluded from search)
curl -s -X PATCH http://localhost:8000/api/v1/gallery/identities/$IDENTITY_ID/consent \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"revoked":true}'
```

### Export subject data (viewer+) and delete (operator+, irreversible)

```bash
curl -s http://localhost:8000/api/v1/gallery/identities/$IDENTITY_ID/export \
  -H "Authorization: Bearer $TOKEN"       # -> {identity, consents, enrollments, exported_at}

curl -s -X DELETE http://localhost:8000/api/v1/gallery/identities/$IDENTITY_ID \
  -H "Authorization: Bearer $TOKEN"       # -> 204, purges identity + consents + templates
```

---

## Admin

```bash
# Users (admin)
curl -s http://localhost:8000/api/v1/admin/users -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"email":"ops@jarvas.dev","full_name":"Ops User","password":"a-strong-password","role":"operator"}'
curl -s -X PATCH http://localhost:8000/api/v1/admin/users/$USER_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"role":"auditor","is_active":true}'

# Audit trail (auditor+) — append-only
curl -s "http://localhost:8000/api/v1/admin/audit?action=identity.enroll&page=1&size=50" \
  -H "Authorization: Bearer $TOKEN"

# Models (auditor+) and metrics (admin)
curl -s http://localhost:8000/api/v1/admin/models -H "Authorization: Bearer $TOKEN"
curl -s http://localhost:8000/api/v1/admin/metrics -H "Authorization: Bearer $TOKEN"

# Retention policies (list: auditor+; create/delete/run: admin)
curl -s http://localhost:8000/api/v1/admin/retention -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/api/v1/admin/retention \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Media 90d","resource_type":"media","retention_days":90,"action":"delete","is_default":false}'
curl -s -X POST http://localhost:8000/api/v1/admin/retention/run -H "Authorization: Bearer $TOKEN"
curl -s -X DELETE http://localhost:8000/api/v1/admin/retention/$POLICY_ID -H "Authorization: Bearer $TOKEN"
```

`resource_type`: `media | identity | audit | video` · `action`: `delete | anonymize`.

---

## Health

```bash
curl -s http://localhost:8000/api/v1/health/live        # liveness (no auth)
curl -s http://localhost:8000/api/v1/health/ready       # readiness incl. DB (no auth)
curl -s http://localhost:8000/api/v1/health             # components + model status (no auth)
curl -s http://localhost:8000/api/v1/health/metrics -H "Authorization: Bearer $TOKEN"   # admin
```

`/health` reports each component's status and, per model, `{provider, loaded, is_mock}` — so you can
confirm whether the real engine or the deterministic mock is running.

---

## Error format

```json
{ "detail": "Incorrect email or password" }
```

Validation errors return a structured `detail` (FastAPI/Pydantic), e.g.
`{"detail":{"message":"...","reasons":["..."]}}` for enrollment rejections. Cross-tenant and missing
resources return `404` uniformly.
