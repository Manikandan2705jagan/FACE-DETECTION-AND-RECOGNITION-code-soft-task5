# JARVAS — Face Detection & Recognition

A premium, **privacy-first** AI web application for detecting faces in images and videos, with an
**optional** consent-gated recognition mode that searches only a local, explicitly-consented identity
gallery.

> This system is designed for **consensual, accountable** use cases only (e.g. verifying a person who
> enrolled themselves, flagging candidates for **manual human review**). It is **not** a surveillance
> tool. It performs no live tracking, public-face search, scraping, emotion analysis, demographic
> profiling, or law-enforcement workflow. See `docs/PRIVACY_POLICY.md` and `docs/THREAT_MODEL.md`.

---

## Highlights

- **Detection-only by default.** A face box, confidence, landmarks and processing time — no identity.
- **Recognition is opt-in and consent-gated.** Embeddings are stored encrypted at rest, only for people
  who gave explicit, purpose-bound, expiring consent.
- **Never certain.** Every match is reported with a cosine similarity, the configured threshold, and a
  `manual_review_required` flag. Results are labelled *candidate*, never *identity*.
- **Privacy engineering built in.** EXIF stripped on upload, Fernet-encrypted embeddings, retention
  policies with irreversible deletion, append-only audit trail.
- **Premium dark UI.** Navy/indigo/cyan/teal glassmorphism, Framer Motion, accessible components.

## Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | Next.js (App Router) · TypeScript · Tailwind CSS · shadcn/ui · Framer Motion |
| Backend    | FastAPI · Pydantic v2 · SQLAlchemy 2 · PostgreSQL + pgvector · Redis |
| AI         | InsightFace (SCRFD detection, ArcFace embeddings) · ONNX Runtime (optional TensorRT) |
| Storage    | S3-compatible object storage (MinIO in dev) |
| Auth       | OAuth2/OIDC + JWT with role-based access control, multi-tenant isolation |
| Deploy     | Docker · Docker Compose · GitHub Actions |

## Repository layout

```
frontend/   Next.js application (dashboard, detect, video, recognize, enroll, gallery, admin)
backend/    FastAPI application, AI services, models, tests
infra/      Docker, compose, nginx, CI workflows, DB init
docs/       Architecture, threat model, setup, API examples, privacy, licensing, calibration
```

## Quick start (Docker)

```bash
cp .env.example .env          # then edit secrets
docker compose -f infra/docker-compose.yml up --build
# Frontend  http://localhost:3000
# API docs  http://localhost:8000/docs
# MinIO     http://localhost:9001
```

Seed synthetic-only demo data (no real faces):

```bash
docker compose -f infra/docker-compose.yml exec backend python -m app.seed
```

## Local development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

SQLite is used automatically when `DATABASE_URL` is unset (dev convenience); Postgres + pgvector is
used when configured. The face engine falls back to a deterministic mock when model weights are not
present, so the app always runs.

## Documentation

- [Setup](docs/SETUP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Threat model](docs/THREAT_MODEL.md)
- [API examples](docs/API_EXAMPLES.md)
- [Privacy policy](docs/PRIVACY_POLICY.md)
- [Model licensing](docs/MODEL_LICENSING.md)
- [Calibration guidance](docs/CALIBRATION.md)

## License

Code: MIT (see `LICENSE`). **Model weights carry their own licenses** — InsightFace pretrained models
are for **non-commercial research** use unless separately licensed. Read `docs/MODEL_LICENSING.md`
before any commercial deployment.
