"""Audit trail service.

Every security-relevant action is appended here. Writes are best-effort and
never block the primary request on failure (failures are logged).
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.audit import AuditLog

logger = get_logger(__name__)


def _client_meta(request: Any) -> tuple[str, str]:
    if request is None:
        return "", ""
    ip = ""
    try:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        elif request.client:
            ip = request.client.host or ""
    except Exception:  # pragma: no cover
        ip = ""
    ua = ""
    try:
        ua = request.headers.get("user-agent", "")[:400]
    except Exception:  # pragma: no cover
        ua = ""
    return ip, ua


def record(
    db: Session,
    *,
    tenant_id: str,
    action: str,
    actor_user_id: Optional[str] = None,
    actor_email: str = "",
    resource_type: str = "",
    resource_id: str = "",
    outcome: str = "success",
    detail: Optional[dict[str, Any]] = None,
    request: Any = None,
    commit: bool = True,
) -> AuditLog:
    ip, ua = _client_meta(request)
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        ip_address=ip,
        user_agent=ua,
        detail=json.dumps(detail or {}, default=str),
    )
    try:
        db.add(entry)
        if commit:
            db.commit()
    except Exception as exc:  # pragma: no cover - never break the request
        logger.error("Audit write failed for action=%s: %s", action, exc)
        db.rollback()
    logger.info(
        "audit",
        extra={"action": action, "outcome": outcome, "tenant_id": tenant_id,
               "user_id": actor_user_id},
    )
    return entry
