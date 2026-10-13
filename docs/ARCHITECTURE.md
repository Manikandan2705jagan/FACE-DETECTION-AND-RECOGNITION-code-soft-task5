# Architecture

JARVAS is a multi-tenant, privacy-first face **detection** service with an optional, consent-gated
**recognition** mode. Detection is the default; recognition is opt-in and always advisory.

---

## 1. High-level topology

```
                      ┌──────────────────────────┐
                      │        Browser           │
                      │  Next.js 15 App Router   │
                      │  Tailwind · shadcn · Framer│
                      └─────────────┬────────────┘
                                    │  HTTPS (JSON + multipart)
                                    ▼
                      ┌──────────────────────────┐
                      │  nginx (optional, :8080) │  reverse proxy, TLS term.
                      └─────────────┬────────────┘
                                    ▼
        ┌───────────────────────────────────────────────────────┐
        │                    FastAPI (api)                      │
        │  auth · images · videos · gallery · admin · health    │
        │  RBAC deps · audit · validation                       │
        └───────┬───────────────┬───────────────┬──────────────┘
                │               │               │
                ▼               ▼               ▼
        ┌────────────┐   ┌────────────┐   ┌──────────────────┐
        │ Postgres   │   │  Redis     │   │  S3 / MinIO      │
        │ +pgvector  │   │ broker/    │   │ uploads + results│
        │ (metadata) │   │ cache      │   │                  │
        └────────────┘   └─────┬──────┘   └──────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
        ┌────────────┐                ┌────────────┐
        │  worker    │                │   beat     │
        │ video jobs │                │ retention  │
        │ +retention │                │ schedule   │
        └─────┬──────┘                └────────────┘
              ▼
        ┌──────────────────────────────────────────┐
        │ Face engine (InsightFace ONNX / mock)     │
        │ SCRFD detection · ArcFace 512-d embeddings│
        └──────────────────────────────────────────┘
```

---

## 2. Core principles encoded in the architecture

1. **Detection-first.** The default pipeline never searches the gallery and never attaches identity.
2. **Consent before biometrics.** An `Enrollment` cannot exist without an active `ConsentRecord`.
3. **Encryption at rest.** Embeddings are Fernet-encrypted before storage; plaintext templates never
   touch the database or object store.
4. **Never certain.** Recognition returns candidates with `manual_review_required=true` and a status
   of `candidate`/`no_match`. No endpoint asserts a confirmed identity.
5. **Irreversible deletion.** Revoking consent disables templates immediately; deletion purges rows
   and objects. Both are audited.
6. **Tenant isolation.** Every tenant-scoped row carries `tenant_id`; all queries filter by the
   caller's tenant. Cross-tenant access returns 404, not 403 (no existence leak).

---

## 3. Backend layering

```
app/
  main.py            FastAPI app factory, lifespan bootstrap, static /media (local storage)
  api/v1/            Routers: auth, images, videos, gallery, admin, health
  core/
    config.py        Pydantic settings (env-driven, safe dev defaults)
    security.py      Role enum, RBAC ranks, bcrypt hashing, JWT issue/verify
    deps.py          get_current_user, require_role(...)
    logging.py       Structured logging setup
  db/                Engine/session, Base + mixins (UUID, timestamps, TenantScoped)
  models/            SQLAlchemy 2 models (tenant, user, identity, media, audit, retention)
  schemas/           Pydantic v2 request/response models
  services/          Domain logic (pipeline, enrollment, gallery, quality, crypto, ...)
  celery_app.py      Celery app + beat schedule
  tasks.py           process_video_job, retention_sweep
  seed.py            Synthetic-only demo seed
  tests/             pytest suite (45 tests)
```

### Request lifecycle (image detection)

```
POST /api/v1/images/detect
  → require_role(viewer)              # authn + authz
  → validate_image_upload(raw)        # type, size, decode, EXIF strip  → UploadRejected
  → store original (S3/local)
  → pipeline.run_image_pipeline()
        face_engine.detect()          # boxes + landmarks + confidence
        quality.evaluate_face()       # blur / lighting / pose / size
        annotate.draw()               # annotated JPEG
        (recognition mode only) gallery.search() → candidates
  → persist MediaAsset + FaceDetection, store annotated result
  → audit_record(action="image.detect")
  → DetectionResponse(detections, ...)
```

### Video pipeline

- Upload validates type/size/duration, stores the source, creates a `VideoJob` (`queued`).
- Processing (Celery `process_video_job`, inline fallback if the broker is down) samples frames at
  `sample_fps`, runs detection per frame, and builds a **face-count timeline**.
- Writes a JSON report to storage; `GET /videos/{id}/report` reconstructs the timeline.
- Detection-only: no identity, no cross-frame tracking, no demographics/emotion.

---

## 4. Data model (abridged)

```
Tenant ─┬─ User (role: viewer|operator|auditor|admin)
        ├─ Identity ─┬─ ConsentRecord   (purpose, expires_at, retention_until,
        │            │                   revoked_at, consent_text_version, evidence_hash)
        │            └─ Enrollment      (encrypted embedding, quality_score, status)
        ├─ MediaAsset ─┬─ FaceDetection (bbox, confidence, landmarks, quality)
        │              └─ VideoJob      (status, progress, frames, timeline report)
        ├─ RecognitionResult            (candidate cosine similarity + threshold)
        ├─ AuditLog                     (append-only)
        └─ RetentionPolicy
```

Notes:
- IDs are UUIDs; timestamps are timezone-aware UTC.
- `Enrollment.embedding_ciphertext` holds Fernet ciphertext; `embedding_dim` is metadata only.
- `RecognitionResult` stores the similarity and threshold but is always paired with an advisory
  notice; it is never treated as ground truth.

---

## 5. Why encrypted embeddings + in-process cosine search?

Production Postgres is provisioned with **pgvector**, yet JARVAS intentionally does **not** index
plaintext templates for ANN search. Storing plaintext biometric vectors in an index would defeat the
"encrypted at rest" guarantee. Instead:

- Embeddings are stored as Fernet ciphertext.
- Gallery search decrypts the caller's tenant's **active, consented** embeddings in-process and runs
  an exact cosine scan with NumPy.

This keeps biometrics encrypted at rest and makes consent revocation trivially effective (a revoked
template is simply excluded from the candidate set). For very large galleries an opt-in,
tenant-held-key ANN design can be layered on later — see `docs/THREAT_MODEL.md`.

---

## 6. Face engine & mock fallback

`services/face_engine.py` exposes a single interface:

- **Real engine:** InsightFace (SCRFD detector + ArcFace 512-d embeddings) via ONNX Runtime.
- **Mock engine:** deterministic — detects one centred face for sufficiently textured images, and
  derives embeddings from an image-content hash (same pixels → same vector). Used when weights are
  missing or `ALLOW_MOCK_FACE_ENGINE=true` and no weights are present.

`engine.model_info()` reports `{provider, loaded, is_mock}` and is surfaced via `/health` and
`/admin/models` so operators always know which engine is live.

---

## 7. Frontend architecture

- **App Router** with a `(dashboard)` route group guarded by the auth provider.
- `lib/api.ts` — typed client; attaches the bearer token, handles 401 by clearing the token.
- `components/ui/*` — accessible shadcn-style primitives.
- `components/jarvas/*` — app shell, dropzone, animated face canvas overlay, privacy banners,
  role guard, page headers.
- Role-aware navigation hides operator/auditor/admin areas from lower roles; destructive actions
  require confirmation.

---

## 8. Operations

- **Health:** `GET /health/live` (liveness), `/health/ready` (DB), `/health` (full component +
  model status), `/health/metrics` and `/admin/metrics` (tenant metrics, admin).
- **Retention:** `celery beat` runs `retention_sweep` daily at 03:00 UTC; also runnable on demand via
  `POST /admin/retention/run`.
- **Audit:** every security-relevant action is appended to `audit_logs` with actor, action, resource,
  outcome, IP, and a detail payload. The table is append-only by convention and should be shipped to
  immutable storage in production.
