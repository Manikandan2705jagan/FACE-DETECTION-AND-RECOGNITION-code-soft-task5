"""Celery application factory + beat schedule."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "jarvas",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_max_tasks_per_child=20,
)

celery_app.conf.beat_schedule = {
    "purge-biometrics-daily": {
        "task": "app.tasks.retention_sweep",
        "schedule": crontab(hour=3, minute=0),
    },
}
