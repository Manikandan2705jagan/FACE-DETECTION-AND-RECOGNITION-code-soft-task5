"""FastAPI application entrypoint for JARVAS."""
from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

DESCRIPTION = """
**JARVAS** is a privacy-first face **detection** service with an optional,
consent-gated **recognition** mode that searches only a local identity gallery.

### Principles
- Detection is the **default**; no identity is inferred.
- Recognition is **opt-in**, searches only identities that gave **explicit consent**,
  and always returns **candidates requiring manual review** — never a certain identity.
- Biometric templates are **encrypted at rest**; uploads are **EXIF-stripped**;
  deletion is **irreversible**; security actions are written to an **audit trail**.

This API does **not** offer live tracking, public-face search, scraping, emotion
analysis, demographic profiling, or law-enforcement workflows.
"""


def _bootstrap() -> None:
    """Create default tenant/admin + default retention policy if missing."""
    from sqlalchemy import select

    from app.core.security import Role, hash_password
    from app.db.session import SessionLocal
    from app.models.retention import RetentionPolicy
    from app.models.tenant import Tenant
    from app.models.user import User

    db = SessionLocal()
    try:
        tenant = db.execute(select(Tenant).limit(1)).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name=settings.bootstrap_tenant_name, slug="default")
            db.add(tenant)
            db.flush()
            logger.info("Bootstrapped tenant '%s'", tenant.slug)

        admin = db.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == settings.bootstrap_admin_email.lower())
        ).scalar_one_or_none()
        if admin is None:
            admin = User(
                tenant_id=tenant.id,
                email=settings.bootstrap_admin_email.lower(),
                full_name="JARVAS Admin",
                hashed_password=hash_password(settings.bootstrap_admin_password),
                role=Role.ADMIN.value,
            )
            db.add(admin)
            logger.info("Bootstrapped admin '%s'", settings.bootstrap_admin_email)

        default_policy = db.execute(
            select(RetentionPolicy).where(
                RetentionPolicy.tenant_id == tenant.id, RetentionPolicy.is_default.is_(True)
            )
        ).scalar_one_or_none()
        if default_policy is None:
            db.add(
                RetentionPolicy(
                    tenant_id=tenant.id, name="Default media retention",
                    resource_type="media", retention_days=settings.default_retention_days,
                    action="delete", is_default=True,
                )
            )
        db.commit()
    except Exception as exc:  # pragma: no cover
        logger.error("Bootstrap failed: %s", exc)
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    logger.info("Starting JARVAS %s (%s)", __version__, settings.env)
    from app.db.session import init_db

    init_db()
    _bootstrap()

    # Warm the face engine off the critical path.
    def _warm() -> None:
        try:
            from app.services.face_engine import warm_up

            warm_up()
        except Exception as exc:  # pragma: no cover
            logger.warning("Face engine warm-up skipped: %s", exc)

    threading.Thread(target=_warm, daemon=True).start()
    yield
    logger.info("Shutting down JARVAS")


def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVAS Face Detection & Recognition API",
        description=DESCRIPTION,
        version=__version__,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Serve local storage in dev so annotated images/reports are downloadable.
    if settings.storage_backend.lower() == "local":
        os.makedirs(os.path.join("data", "storage"), exist_ok=True)
        app.mount("/media", StaticFiles(directory=os.path.join("data", "storage")), name="media")

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
            "privacy": "Detection-only by default. Recognition is consent-gated and never certain.",
        }

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        logger.error("Unhandled error on %s: %s", request.url.path, exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error", "code": "internal_error"})

    return app


app = create_app()
