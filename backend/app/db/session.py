"""SQLAlchemy engine / session factory.

Works with PostgreSQL (+ pgvector for ANN recognition) and, as a development
convenience, SQLite when no ``DATABASE_URL`` is provided.
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_url = settings.resolved_database_url

if settings.use_sqlite:
    db_path = _url.replace("sqlite+pysqlite:///", "")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

_connect_args = {"check_same_thread": False} if settings.use_sqlite else {}

engine = create_engine(
    _url,
    echo=False,
    future=True,
    pool_pre_ping=not settings.use_sqlite,
    connect_args=_connect_args,
)

if settings.use_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - env specific
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables (dev / test convenience; production uses Alembic)."""
    from app.db.base import Base  # noqa: WPS433 (circular-safe import)

    # Ensure all models are imported so they register on the metadata.
    from app import models  # noqa: F401,WPS433

    if settings.use_sqlite is False:
        try:  # enable pgvector when present
            from sqlalchemy import text

            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:  # pragma: no cover - extension may be missing
            pass

    Base.metadata.create_all(bind=engine)
