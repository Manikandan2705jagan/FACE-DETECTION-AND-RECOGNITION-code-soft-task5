# Setup

This guide covers running JARVAS locally with Docker, running it without Docker, and preparing
production configuration.

---

## 1. Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Docker + Compose | v24+ | Recommended path |
| Python | 3.11 | Backend (3.10–3.12 also work) |
| Node.js | 20 LTS | Frontend |
| `openssl` | any | Generate secrets |

Model weights are **optional** to run: if they are absent the backend uses a deterministic mock
face engine so the app still works end to end (`ALLOW_MOCK_FACE_ENGINE=true`).

---

## 2. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and, at minimum, replace:

- `JWT_SECRET` — `openssl rand -hex 32`
- `BOOTSTRAP_ADMIN_PASSWORD` — a strong first admin password
- `POSTGRES_PASSWORD`
- `S3_SECRET_KEY` (MinIO)
- `BIOMETRIC_ENCRYPTION_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

> In development the embedding encryption key is derived from `JWT_SECRET` if
> `BIOMETRIC_ENCRYPTION_KEY` is empty, but production **must** set it explicitly.

---

## 3. Run with Docker (recommended)

```bash
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API + Swagger | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |

Optional: run everything behind a single nginx entrypoint on `:8080`:

```bash
docker compose -f infra/docker-compose.yml --env-file .env --profile proxy up --build
# http://localhost:8080  (web + /api/* + /media/*)
```

On first boot the backend creates the tenant, the bootstrap admin, and a default retention policy.
Sign in with `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`.

### Seed synthetic-only demo data

No real faces are downloaded or generated. Synthetic, procedurally-textured faces are used.

```bash
docker compose -f infra/docker-compose.yml exec backend python -m app.seed
```

---

## 4. Run without Docker (local development)

**Backend**

```bash
cd backend
python -m venv .venv
# Windows:          .venv\Scripts\activate
# macOS / Linux:    source .venv/bin/activate
pip install -r requirements.txt      # heavy; installs insightface/onnxruntime
uvicorn app.main:app --reload
```

When `DATABASE_URL` is unset the backend uses a local SQLite file (`backend/data/jarvas.sqlite3`)
and, if `STORAGE_BACKEND=local`, writes files under `backend/data/storage` (served at `/media`).

Skip the heavy AI deps for a quick spin (mock engine):

```bash
pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings \
  email-validator sqlalchemy cryptography "python-jose[cryptography]" bcrypt \
  pillow numpy opencv-python-headless httpx pytest pytest-asyncio
```

**Frontend**

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

Point the frontend at the API with `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`).

---

## 5. Tests & quality gates

```bash
# Backend
cd backend && pytest -q

# Frontend
cd frontend && npm run typecheck && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs the backend test suite, the frontend typecheck/lint/build, and
validates the compose file.

---

## 6. Model weights (optional, for real inference)

Without weights the mock engine is used. To enable real InsightFace detection + recognition:

1. Download an InsightFace model pack (e.g. `buffalo_sc`) — read `MODEL_LICENSING.md` first.
2. Place it under the mounted `models` volume (default `/models`), or set `MODEL_DIR` to its path.
3. Restart the backend. `/api/v1/health` and `/api/v1/admin/models` show `is_mock: false` once loaded.
4. For GPU builds use `infra/backend.Dockerfile.gpu` and set `FACE_PROVIDERS=CUDAExecutionProvider`.

---

## 7. Production checklist

- [ ] `JARVAS_ENV=production`, strong `JWT_SECRET`, explicit `BIOMETRIC_ENCRYPTION_KEY`
- [ ] TLS terminated in front of the API/web (nginx, ALB, etc.); set `CORS_ORIGINS` to real origins
- [ ] `STORAGE_BACKEND=s3` with private buckets and least-privilege credentials
- [ ] Managed Postgres with `pgvector`; backups encrypted
- [ ] Set `RECOGNITION_ENABLED` deliberately (defaults to on; set to `false` for detection-only)
- [ ] Calibrate `DEFAULT_SIMILARITY_THRESHOLD` per use case (see `CALIBRATION.md`)
- [ ] Retention policies reviewed and a scheduled sweep confirmed (`celery beat`)
- [ ] Audit log shipped to append-only storage
