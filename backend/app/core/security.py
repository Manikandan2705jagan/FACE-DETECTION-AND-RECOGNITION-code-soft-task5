"""Auth primitives: password hashing, JWT issuance/verification, roles.

Kept dependency-light so it can be unit-tested without a database.
"""
from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

# bcrypt only considers the first 72 bytes; truncate explicitly so long
# passwords never raise on modern bcrypt releases.
_BCRYPT_MAX_BYTES = 72


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(plain), hashed.encode())
    except Exception:  # pragma: no cover - defensive
        return False


class Role(str, enum.Enum):
    VIEWER = "viewer"        # read-only: can run detection, cannot enroll or recognize
    OPERATOR = "operator"    # detection + enrollment (with consent) + recognition
    AUDITOR = "auditor"      # read-only + full audit trail access
    ADMIN = "admin"          # everything, incl. users/roles/retention/health


# Ordered privilege for simple hierarchy checks.
_ROLE_RANK = {Role.VIEWER: 0, Role.AUDITOR: 1, Role.OPERATOR: 2, Role.ADMIN: 3}


def role_at_least(role: Role, required: Role) -> bool:
    return _ROLE_RANK.get(role, -1) >= _ROLE_RANK.get(required, 99)


def create_access_token(
    subject: str,
    *,
    secret: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str, algorithm: str = "HS256") -> Dict[str, Any]:
    """Decode a JWT or raise ``JWTError``."""
    return jwt.decode(token, secret, algorithms=[algorithm])


__all__ = [
    "Role",
    "role_at_least",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "JWTError",
]
