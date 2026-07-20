"""Authentication service – registration, login, token management."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from api.config import get_settings
from api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

_MOCK_SMS_CODE = "123456"


class AuthService:
    """User registration, password verification, and JWT token management."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, phone: str, password: str, sms_code: str | None = None) -> dict:
        """Create a new user and return a user dict.

        In mock mode (default), the SMS code ``123456`` is always accepted.
        Raises ``ValueError`` if the phone number is already registered or the
        SMS code is wrong.
        """
        # Verify SMS code (mock)
        if sms_code is not None and sms_code != _MOCK_SMS_CODE:
            raise ValueError("Invalid SMS verification code")

        # Check for existing user
        cur = self._conn.execute(
            "SELECT id FROM users WHERE phone = ?", (phone,)
        )
        if cur.fetchone() is not None:
            raise ValueError("Phone number already registered")

        pw_hash = hash_password(password)
        now = datetime.now(timezone.utc).isoformat()

        cur = self._conn.execute(
            "INSERT INTO users (phone, password_hash, created_at, last_login_at) "
            "VALUES (?, ?, ?, ?)",
            (phone, pw_hash, now, now),
        )
        self._conn.commit()
        user_id = cur.lastrowid

        return {
            "id": user_id,
            "phone": phone,
            "created_at": now,
        }

    # ------------------------------------------------------------------
    # Password verification
    # ------------------------------------------------------------------

    def verify_password(self, phone: str, password: str) -> dict | None:
        """Find user by phone and verify password.

        Returns user dict on success, ``None`` on failure.
        """
        cur = self._conn.execute(
            "SELECT id, phone, password_hash, created_at FROM users WHERE phone = ?",
            (phone,),
        )
        row = cur.fetchone()
        if row is None:
            return None

        user_id, user_phone, pw_hash, created_at = row
        if not verify_password(password, pw_hash):
            return None

        # Update last_login_at
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id)
        )
        self._conn.commit()

        return {
            "id": user_id,
            "phone": user_phone,
            "created_at": created_at,
        }

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def create_tokens(self, user_id: int) -> dict:
        """Create access + refresh token pair for *user_id*."""
        s = self._settings
        access = create_access_token(
            user_id, s.JWT_SECRET, s.JWT_ALGORITHM, s.ACCESS_TOKEN_EXPIRE_MIN,
        )
        refresh = create_refresh_token(
            user_id, s.JWT_SECRET, s.JWT_ALGORITHM, s.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
        }

    def refresh_access_token(self, refresh_token: str) -> dict:
        """Decode refresh token and issue a new access token.

        Raises ``ValueError`` if the refresh token is invalid or expired.
        """
        from jose import JWTError

        s = self._settings
        try:
            payload = decode_token(refresh_token, s.JWT_SECRET, s.JWT_ALGORITHM)
        except JWTError:
            raise ValueError("Invalid or expired refresh token")

        if payload.get("type") != "refresh":
            raise ValueError("Token is not a refresh token")

        user_id = int(payload["sub"])
        access = create_access_token(
            user_id, s.JWT_SECRET, s.JWT_ALGORITHM, s.ACCESS_TOKEN_EXPIRE_MIN,
        )
        new_refresh = create_refresh_token(
            user_id, s.JWT_SECRET, s.JWT_ALGORITHM, s.REFRESH_TOKEN_EXPIRE_DAYS,
        )
        return {
            "access_token": access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
        }

    def get_user_by_id(self, user_id: int | str) -> dict | None:
        """Return user info dict for the given user_id, or None."""
        cur = self._conn.execute(
            "SELECT id, phone, created_at FROM users WHERE id = ?",
            (int(user_id),),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "phone": row[1],
            "created_at": row[2],
        }
