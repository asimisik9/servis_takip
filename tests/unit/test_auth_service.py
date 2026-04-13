from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status
from jose import jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    REFRESH_SECRET_KEY,
    SECRET_KEY,
    create_refresh_token,
    hash_password,
)
from app.services.auth_service import AuthService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_for_valid_credentials(
    mock_db_session, make_execute_result, sample_users
):
    user = sample_users["tenant_admin"]
    user.password_hash = hash_password("StrongPass1")
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=user)

    service = AuthService(mock_db_session)
    result = await service.authenticate_user(user.email, "StrongPass1")

    assert result is user


@pytest.mark.asyncio
async def test_authenticate_user_returns_none_for_invalid_password(
    mock_db_session, make_execute_result, sample_users
):
    user = sample_users["tenant_admin"]
    user.password_hash = hash_password("StrongPass1")
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=user)

    service = AuthService(mock_db_session)
    result = await service.authenticate_user(user.email, "WrongPass1")

    assert result is None


@pytest.mark.asyncio
async def test_authenticate_user_rejects_inactive_user(
    mock_db_session, make_execute_result, sample_users
):
    user = sample_users["inactive_user"]
    user.password_hash = hash_password("StrongPass1")
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=user)

    service = AuthService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.authenticate_user(user.email, "StrongPass1")

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Account is deactivated. Contact an administrator."


@pytest.mark.asyncio
async def test_create_tokens_contains_expected_claims(sample_users):
    service = AuthService(db=None)

    access_token, refresh_token = await service.create_tokens(sample_users["tenant_admin"])

    access_payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
    refresh_payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

    assert access_payload["sub"] == sample_users["tenant_admin"].email
    assert access_payload["id"] == sample_users["tenant_admin"].id
    assert access_payload["role"] == sample_users["tenant_admin"].role.value
    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"


@pytest.mark.asyncio
async def test_logout_revokes_access_and_refresh_tokens(sample_users):
    user = sample_users["tenant_admin"]
    service = AuthService(db=None)
    service._blacklist_token = AsyncMock()

    access_token, refresh_token = await service.create_tokens(user)

    await service.logout(
        access_token,
        refresh_token=refresh_token,
        current_user_id=user.id,
        current_user_email=user.email,
    )

    assert service._blacklist_token.await_count == 2
    revoked_tokens = [call.args[0] for call in service._blacklist_token.await_args_list]
    assert revoked_tokens == [access_token, refresh_token]


@pytest.mark.asyncio
async def test_logout_rejects_refresh_token_for_different_user(sample_users):
    user = sample_users["tenant_admin"]
    other_user = sample_users["transport_driver"]
    service = AuthService(db=None)
    service._blacklist_token = AsyncMock()

    access_token, _ = await service.create_tokens(user)
    mismatched_refresh = create_refresh_token(
        {"sub": other_user.email, "id": other_user.id, "role": other_user.role.value}
    )

    with pytest.raises(HTTPException) as exc:
        await service.logout(
            access_token,
            refresh_token=mismatched_refresh,
            current_user_id=user.id,
            current_user_email=user.email,
        )

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc.value.detail == "Could not validate credentials"
    service._blacklist_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_logout_ignores_already_expired_refresh_token(sample_users):
    user = sample_users["tenant_admin"]
    service = AuthService(db=None)
    service._blacklist_token = AsyncMock()

    access_token, _ = await service.create_tokens(user)
    expired_refresh = create_refresh_token(
        {"sub": user.email, "id": user.id, "role": user.role.value},
        expires_delta=timedelta(minutes=-1),
    )

    await service.logout(
        access_token,
        refresh_token=expired_refresh,
        current_user_id=user.id,
        current_user_email=user.email,
    )

    service._blacklist_token.assert_awaited_once()
    assert service._blacklist_token.await_args.args[0] == access_token


@pytest.mark.asyncio
async def test_forgot_password_cleans_up_token_when_email_dispatch_fails(
    mock_db_session,
    make_execute_result,
    sample_users,
    fake_redis,
    compiled_sql,
    monkeypatch,
):
    user = sample_users["tenant_admin"]
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=user),
        make_execute_result(),
    ]

    service = AuthService(mock_db_session)
    service._validate_password_reset_configuration = lambda: None
    service._send_password_reset_email = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset email could not be sent. Please try again.",
        )
    )
    monkeypatch.setattr("app.services.auth_service.redis_manager", fake_redis)

    with pytest.raises(HTTPException) as exc:
        await service.forgot_password(
            email=user.email,
            requested_ip="127.0.0.1",
            requested_user_agent="pytest",
        )

    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert mock_db_session.add.call_count == 1
    assert mock_db_session.commit.await_count == 2
    cleanup_stmt = mock_db_session.execute.await_args_list[1].args[0]
    assert "DELETE FROM password_reset_tokens" in compiled_sql(cleanup_stmt)
    fake_redis.set.assert_awaited_once()


def test_password_reset_configuration_guard_lists_missing_fields(monkeypatch):
    service = AuthService(db=None)
    monkeypatch.setattr(settings, "SMTP_HOST", None)
    monkeypatch.setattr(settings, "PASSWORD_RESET_URL_BASE", None)

    with pytest.raises(HTTPException) as exc:
        service._validate_password_reset_configuration()

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "SMTP_HOST" in exc.value.detail
    assert "PASSWORD_RESET_URL_BASE" in exc.value.detail


def test_email_verification_configuration_guard_lists_missing_fields(monkeypatch):
    service = AuthService(db=None)
    monkeypatch.setattr(settings, "SMTP_USERNAME", None)
    monkeypatch.setattr(settings, "EMAIL_VERIFY_REDIRECT_URL", None)

    with pytest.raises(HTTPException) as exc:
        service._validate_email_verification_configuration()

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "SMTP_USERNAME" in exc.value.detail
    assert "EMAIL_VERIFY_REDIRECT_URL" in exc.value.detail


def test_password_reset_link_builder_preserves_existing_query(monkeypatch):
    service = AuthService(db=None)
    monkeypatch.setattr(settings, "PASSWORD_RESET_URL_BASE", "http://localhost/reset-password?source=admin")

    reset_link = service._build_password_reset_link("token-123")
    parsed = urlparse(reset_link)
    query = parse_qs(parsed.query)

    assert parsed.path == "/reset-password"
    assert query["source"] == ["admin"]
    assert query["token"] == ["token-123"]


def test_build_redirect_url_with_status_preserves_existing_query():
    redirect_url = AuthService._build_redirect_url_with_status(
        "http://localhost/email-verified?source=admin",
        "success",
    )
    parsed = urlparse(redirect_url)
    query = parse_qs(parsed.query)

    assert parsed.path == "/email-verified"
    assert query["source"] == ["admin"]
    assert query["status"] == ["success"]


def test_email_verification_link_builder_adds_token(monkeypatch):
    service = AuthService(db=None)
    monkeypatch.setattr(settings, "API_V1_STR", "/api")

    verification_link = service._build_email_verification_link("verify-123", "http://localhost:8000/")
    parsed = urlparse(verification_link)
    query = parse_qs(parsed.query)

    assert parsed.path == "/api/auth/verify-email"
    assert query["token"] == ["verify-123"]
