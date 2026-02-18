from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.security import is_token_stale_for_password_change
from app.dependencies import _is_unverified_access_allowed
from app.database.schemas.auth import ChangePasswordRequest, ResetPasswordRequest
from app.database.schemas.user import User, UserRole


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


def test_reset_password_request_validates_token():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="   ", new_password="StrongPass1")


def test_change_password_request_validates_password_strength():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password="OldPass1", new_password="weak")


def test_unverified_access_allowlist():
    assert _is_unverified_access_allowed("/api/auth/me") is True
    assert _is_unverified_access_allowed("/api/auth/me/") is True
    assert _is_unverified_access_allowed("/api/auth/resend-email-verification") is True
    assert _is_unverified_access_allowed("/api/driver/buses") is False


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
