from datetime import datetime, timezone

import pytest
from fastapi import HTTPException, status

from app.database.schemas.user import User, UserRole
from app.dependencies import RoleChecker, _is_unverified_access_allowed


pytestmark = pytest.mark.unit


def make_schema_user(role=UserRole.admin, organization_id="org-school-1"):
    return User(
        id="user-1",
        full_name="Test User",
        email="user@example.com",
        phone_number="+905551112233",
        role=role,
        organization_id=organization_id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def test_unverified_access_allowlist():
    assert _is_unverified_access_allowed("/api/auth/me") is True
    assert _is_unverified_access_allowed("/api/auth/me/") is True
    assert _is_unverified_access_allowed("/api/auth/resend-email-verification") is True
    assert _is_unverified_access_allowed("/api/driver/buses") is False


def test_role_checker_returns_user_for_allowed_role():
    checker = RoleChecker(["admin", "super_admin"])
    user = make_schema_user(role=UserRole.admin, organization_id="org-school-1")

    assert checker(user) is user


def test_role_checker_rejects_disallowed_role():
    checker = RoleChecker(["admin"])
    user = make_schema_user(role=UserRole.veli, organization_id="org-school-1")

    with pytest.raises(HTTPException) as exc:
        checker(user)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Operation not permitted"


def test_role_checker_rejects_admin_without_organization():
    checker = RoleChecker(["admin", "super_admin"])
    user = make_schema_user(role=UserRole.admin, organization_id=None)

    with pytest.raises(HTTPException) as exc:
        checker(user)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Admin account is not bound to an organization"
