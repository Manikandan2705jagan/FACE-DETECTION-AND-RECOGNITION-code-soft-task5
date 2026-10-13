"""FastAPI dependencies: authentication, RBAC, current tenant."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import JWTError, Role, decode_token, role_at_least
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _UNAUTH
    try:
        payload = decode_token(
            credentials.credentials,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise _UNAUTH

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")

    # Defence-in-depth: token tenant must match the user's tenant.
    token_tenant = payload.get("tenant_id")
    if token_tenant and token_tenant != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant mismatch")
    return user


def get_current_tenant_id(user: User = Depends(get_current_user)) -> str:
    return user.tenant_id


def require_role(*roles: Role):
    """Dependency factory requiring the user to hold at least one of ``roles``."""
    allowed = set(roles)

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not any(role_at_least(user.role_enum, r) for r in allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(sorted(r.value for r in roles))}",
            )
        return user

    return _checker


def require_permission(permission: str):
    """Coarse permission mapping layered on top of roles."""
    mapping = {
        "detect": {Role.VIEWER},
        "enroll": {Role.OPERATOR},
        "recognize": {Role.OPERATOR},
        "admin": {Role.ADMIN},
        "audit": {Role.AUDITOR},
    }
    roles = mapping.get(permission, {Role.ADMIN})

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not any(role_at_least(user.role_enum, r) for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission}",
            )
        return user

    return _checker


def client_meta(request: Request) -> tuple[str, str]:
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host or ""
    return ip, request.headers.get("user-agent", "")[:400]
