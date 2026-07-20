from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given plaintext password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches the bcrypt *hashed* value."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: int,
    secret: str,
    algorithm: str,
    expire_min: int,
) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expire_min),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(
    user_id: int,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expire_days),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str | None = None, algorithm: str | None = None) -> dict:
    """Decode and validate a JWT, returning the payload dict.

    If *secret* and *algorithm* are omitted, they are loaded from Settings.
    Raises ``JWTError`` if the token is invalid or expired.
    """
    if secret is None or algorithm is None:
        from api.config import get_settings
        s = get_settings()
        secret = secret or s.JWT_SECRET
        algorithm = algorithm or s.JWT_ALGORITHM
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except JWTError:
        raise
