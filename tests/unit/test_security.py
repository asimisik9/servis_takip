from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from pydantic import ValidationError

from app.core.security import (
    ALGORITHM,
    REFRESH_SECRET_KEY,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    hash_password,
    is_token_stale_for_password_change,
    verify_password,
)
from app.database.schemas.auth import ChangePasswordRequest, ResetPasswordRequest
from app.database.schemas.user import User, UserRole


pytestmark = pytest.mark.unit


def test_access_token_contains_type_and_issued_at_claims():
    token = create_access_token({"sub": "user@example.com"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "user@example.com"
    assert payload["type"] == "access"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["iat_ms"], int)
    assert payload["iat_ms"] >= payload["iat"] * 1000


def test_refresh_token_contains_type_and_issued_at_claims():
    token = create_refresh_token({"sub": "user@example.com"})
    payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

    assert payload["sub"] == "user@example.com"
    assert payload["type"] == "refresh"
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["iat_ms"], int)


def test_verify_password_matches_and_rejects_invalid_password():
    password_hash = hash_password("StrongPass1")

    assert verify_password("StrongPass1", password_hash) is True
    assert verify_password("WrongPass1", password_hash) is False


def test_token_without_iat_is_stale_after_password_change():
    payload = {"sub": "user@example.com"}
    changed_at = datetime.now(timezone.utc)

    assert is_token_stale_for_password_change(payload, changed_at) is True


def test_token_not_stale_when_password_never_changed():
    payload = {"sub": "user@example.com", "iat_ms": 1}

    assert is_token_stale_for_password_change(payload, None) is False


def test_token_staleness_uses_millisecond_precision():
    changed_at = datetime.now(timezone.utc)
    old_payload = {"iat_ms": int((changed_at - timedelta(milliseconds=1)).timestamp() * 1000)}
    new_payload = {"iat_ms": int((changed_at + timedelta(milliseconds=1)).timestamp() * 1000)}

    assert is_token_stale_for_password_change(old_payload, changed_at) is True
    assert is_token_stale_for_password_change(new_payload, changed_at) is False


def test_token_staleness_handles_naive_password_changed_at():
    changed_at = datetime(2026, 1, 1, 12, 0, 0)
    changed_at_utc = changed_at.replace(tzinfo=timezone.utc)
    payload = {"iat_ms": int((changed_at_utc.timestamp() + 1) * 1000)}

    assert is_token_stale_for_password_change(payload, changed_at) is False


def test_reset_password_request_validates_token():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="   ", new_password="StrongPass1")


def test_change_password_request_validates_password_strength():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="OldPass1", new_password="weak")


def test_user_schema_has_email_verification_fields():
    user = User(
        id="u1",
        full_name="Test User",
        email="test@example.com",
        phone_number="+905551112233",
        role=UserRole.veli,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    assert user.is_email_verified is False
    assert user.email_verified_at is None
