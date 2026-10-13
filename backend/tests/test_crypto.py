"""Unit tests for cryptographic embedding storage."""
from __future__ import annotations

import numpy as np

from app.services.crypto import (
    decrypt_embedding,
    encrypt_embedding,
    encrypt_json,
    decrypt_json,
)


def test_embedding_roundtrip():
    vec = np.random.RandomState(1).standard_normal(512).astype(np.float32)
    token = encrypt_embedding(vec)
    assert isinstance(token, bytes)
    restored = decrypt_embedding(token, dim=512)
    assert restored.shape == (512,)
    assert np.allclose(vec, restored, atol=1e-5)


def test_embedding_not_plaintext_at_rest():
    vec = np.ones(512, dtype=np.float32)
    token = encrypt_embedding(vec)
    raw = vec.tobytes()
    assert raw not in token
    assert token != raw


def test_json_roundtrip():
    payload = {"a": 1, "b": [1, 2, 3]}
    token = encrypt_json(payload)
    assert decrypt_json(token) == payload
