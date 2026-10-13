"""Authentication endpoints (local JWT + optional OIDC subject linkage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.audit import record as audit_record

router = APIRouter()


def _authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    return user


def _issue(user: User) -> TokenResponse:
    token = create_access_token(
        user.id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.access_token_expire_minutes,
        extra={"role": user.role, "tenant_id": user.tenant_id, "email": user.email},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        role=user.role,
        tenant_id=user.tenant_id,
    )


@router.post("/token", response_model=TokenResponse, summary="Login with email + password")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = _authenticate(db, payload.email, payload.password)
    audit_record(
        db, tenant_id=user.tenant_id, action="auth.login", actor_user_id=user.id,
        actor_email=user.email, request=request,
    )
    return _issue(user)


@router.post("/token/form", response_model=TokenResponse, include_in_schema=False)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(), request: Request = None, db: Session = Depends(get_db)
) -> TokenResponse:
    """OAuth2 password-flow variant (for Swagger 'Authorize' button)."""
    user = _authenticate(db, form.username, form.password)
    audit_record(
        db, tenant_id=user.tenant_id, action="auth.login", actor_user_id=user.id,
        actor_email=user.email, request=request,
    )
    return _issue(user)


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def me(user: User = Depends(get_current_user)) -> User:
    return user
