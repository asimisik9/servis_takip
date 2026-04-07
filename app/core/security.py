from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from .config import settings
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

# Password hashing
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash a password using argon2"""
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    try:
        ph.verify(hashed_password, plain_password)
        return True
    except (VerifyMismatchError, Exception) as e:
        logger.debug(f"Password verification failed: {type(e).__name__}")
        return False

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update(
        {
            "exp": expire,
            "type": "access",
            "iat": int(issued_at.timestamp()),
            "iat_ms": int(issued_at.timestamp() * 1000),
        }
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(timezone.utc)
    if expires_delta:
        expire = issued_at + expires_delta
    else:
        expire = issued_at + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "iat": int(issued_at.timestamp()),
            "iat_ms": int(issued_at.timestamp() * 1000),
        }
    )
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def is_token_stale_for_password_change(payload: dict[str, Any], password_changed_at: datetime | None) -> bool:
    """
    Returns True when token was issued before user's latest password change.
    Tokens without iat/iat_ms are treated as stale once password_changed_at exists.
    """
    if password_changed_at is None:
        return False

    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    else:
        password_changed_at = password_changed_at.astimezone(timezone.utc)

    iat_ms = payload.get("iat_ms")
    if iat_ms is None:
        iat = payload.get("iat")
        if iat is None:
            return True
        try:
            iat_ms = int(float(iat) * 1000)
        except (TypeError, ValueError):
            return True
    else:
        try:
            iat_ms = int(iat_ms)
        except (TypeError, ValueError):
            return True

    password_changed_at_ms = int(password_changed_at.timestamp() * 1000)
    return iat_ms < password_changed_at_ms
