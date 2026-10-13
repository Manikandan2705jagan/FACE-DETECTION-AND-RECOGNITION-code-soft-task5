"""Encryption of biometric embeddings at rest.

Embeddings are serialised to bytes then encrypted with Fernet (AES-128-CBC +
HMAC-SHA256). The encryption key comes from ``BIOMETRIC_ENCRYPTION_KEY``; in
development it is derived deterministically from the JWT secret so the app can
boot without extra configuration. **Production MUST set an explicit key.**
"""
from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Any

import numpy as np
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_DEV_SALT = b"jarvas-biometric-embedding-v1"


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(_DEV_SALT + secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet() -> Fernet:
    key = settings.biometric_encryption_key.strip()
    if not key:
        # Dev fallback: derive from JWT secret so nothing is stored in cleartext.
        key = _derive_key(settings.jwt_secret).decode()
    else:
        # Validate/normalise a provided key.
        try:
            Fernet(key.encode())
        except Exception:
            key = _derive_key(key).decode()
    return Fernet(key.encode())


def encrypt_bytes(data: bytes) -> bytes:
    return _fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    return _fernet().decrypt(token)


def embedding_to_bytes(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype=np.float32).tobytes()


def bytes_to_embedding(data: bytes, dim: int | None = None) -> np.ndarray:
    vector = np.frombuffer(data, dtype=np.float32)
    if dim is not None and vector.size != dim:
        # Non-fatal: still return what we have.
        pass
    return vector


def encrypt_embedding(vector: np.ndarray) -> bytes:
    """Return the encrypted-at-rest representation of an embedding."""
    return encrypt_bytes(embedding_to_bytes(vector))


def decrypt_embedding(token: bytes, dim: int | None = None) -> np.ndarray:
    try:
        raw = decrypt_bytes(token)
    except InvalidToken as exc:  # pragma: no cover - key rotation scenario
        raise ValueError("Failed to decrypt embedding (wrong key?)") from exc
    return bytes_to_embedding(raw, dim=dim)


def encrypt_json(payload: Any) -> str:
    return encrypt_bytes(json.dumps(payload, separators=(",", ":"), default=str).encode()).decode()


def decrypt_json(token: str) -> Any:
    return json.loads(decrypt_bytes(token.encode()).decode())
