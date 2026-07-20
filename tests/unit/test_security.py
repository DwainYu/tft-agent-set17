"""Unit tests for api.core.security (password hashing & JWT)."""
from __future__ import annotations

from datetime import UTC

import pytest
from jose import JWTError

from api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit

SECRET = "test-secret"
ALGO = "HS256"


class TestPasswordHashing:
    """Verify bcrypt password hashing and verification."""

    def test_hash_produces_bcrypt_string(self):
        hashed = hash_password("MyP@ssw0rd")
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("correct-horse", hashed) is True

    def test_verify_incorrect_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("wrong-horse", hashed) is False

    def test_different_hashes_each_time(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # bcrypt salt differs


class TestAccessToken:
    """Verify JWT access-token creation and decoding round-trip."""

    def test_roundtrip(self):
        token = create_access_token(user_id=42, secret=SECRET, algorithm=ALGO, expire_min=30)
        payload = decode_token(token, secret=SECRET, algorithm=ALGO)
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_token_is_string(self):
        token = create_access_token(user_id=1, secret=SECRET, algorithm=ALGO, expire_min=5)
        assert isinstance(token, str)
        assert len(token) > 10

    def test_decode_with_wrong_secret_raises(self):
        token = create_access_token(user_id=1, secret=SECRET, algorithm=ALGO, expire_min=30)
        with pytest.raises(JWTError):
            decode_token(token, secret="wrong-secret", algorithm=ALGO)


class TestRefreshToken:
    """Verify refresh-token creation."""

    def test_refresh_roundtrip(self):
        token = create_refresh_token(user_id=7, secret=SECRET, algorithm=ALGO, expire_days=7)
        payload = decode_token(token, secret=SECRET, algorithm=ALGO)
        assert payload["sub"] == "7"
        assert payload["type"] == "refresh"


class TestTokenExpiration:
    """Verify that expired tokens are rejected."""

    def test_expired_token_raises(self):
        # Create a token that expired 1 minute ago (expire_min=0 means exp == now,
        # but we need it in the past, so use -1 trick)
        from datetime import datetime, timedelta

        from jose import jwt as jose_jwt

        now = datetime.now(UTC)
        payload = {
            "sub": "1",
            "type": "access",
            "iat": now,
            "exp": now - timedelta(minutes=5),  # 5 min ago
        }
        expired_token = jose_jwt.encode(payload, SECRET, algorithm=ALGO)

        with pytest.raises(JWTError):
            decode_token(expired_token, secret=SECRET, algorithm=ALGO)
