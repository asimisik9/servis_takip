import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from app.database.models.organization import Organization, OrganizationType
from app.database.models.user import User as UserModel, UserRole as ModelUserRole


class ExecuteResultStub:
    def __init__(self, *, scalar_one_or_none=None, scalar=None, all_items=None):
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar = scalar
        self._all_items = list(all_items or [])

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._all_items))


@pytest.fixture
def make_execute_result():
    def _make(*, scalar_one_or_none=None, scalar=None, all_items=None):
        return ExecuteResultStub(
            scalar_one_or_none=scalar_one_or_none,
            scalar=scalar,
            all_items=all_items,
        )

    return _make


@pytest.fixture
def mock_db_session():
    session = SimpleNamespace(
        execute=AsyncMock(),
        get=AsyncMock(),
        commit=AsyncMock(),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        rollback=AsyncMock(),
        delete=AsyncMock(),
        add=MagicMock(),
    )
    return session


@pytest.fixture
def sample_org_ids():
    return {
        "school": "org-school-1",
        "transport": "org-transport-1",
        "other": "org-other-1",
    }


@pytest.fixture
def frozen_now():
    return datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_users(sample_org_ids, frozen_now):
    school_org = Organization(
        id=sample_org_ids["school"],
        name="School Org",
        type=OrganizationType.school,
        is_active=True,
        created_at=frozen_now,
    )
    transport_org = Organization(
        id=sample_org_ids["transport"],
        name="Transport Org",
        type=OrganizationType.transport_company,
        is_active=True,
        created_at=frozen_now,
    )
    other_org = Organization(
        id=sample_org_ids["other"],
        name="Other School Org",
        type=OrganizationType.school,
        is_active=True,
        created_at=frozen_now,
    )

    tenant_admin = UserModel(
        id="user-admin-1",
        full_name="Tenant Admin",
        email="tenant.admin@example.com",
        phone_number="+905551110001",
        password_hash="hashed-password",
        role=ModelUserRole.admin,
        organization_id=sample_org_ids["school"],
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )
    tenant_admin.organization = school_org

    super_admin = UserModel(
        id="user-super-1",
        full_name="Super Admin",
        email="super.admin@example.com",
        phone_number="+905551110002",
        password_hash="hashed-password",
        role=ModelUserRole.super_admin,
        organization_id=None,
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )

    orphan_admin = UserModel(
        id="user-orphan-1",
        full_name="Orphan Admin",
        email="orphan.admin@example.com",
        phone_number="+905551110003",
        password_hash="hashed-password",
        role=ModelUserRole.admin,
        organization_id=None,
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )

    inactive_user = UserModel(
        id="user-inactive-1",
        full_name="Inactive User",
        email="inactive.user@example.com",
        phone_number="+905551110004",
        password_hash="hashed-password",
        role=ModelUserRole.admin,
        organization_id=sample_org_ids["school"],
        is_active=False,
        is_email_verified=True,
        created_at=frozen_now,
    )
    inactive_user.organization = school_org

    managed_user = UserModel(
        id="user-managed-1",
        full_name="Managed User",
        email="managed.user@example.com",
        phone_number="+905551110005",
        password_hash="hashed-password",
        role=ModelUserRole.veli,
        organization_id=sample_org_ids["school"],
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )
    managed_user.organization = school_org

    contact_person = UserModel(
        id="user-contact-1",
        full_name="Contact Person",
        email="contact.person@example.com",
        phone_number="+905551110006",
        password_hash="hashed-password",
        role=ModelUserRole.admin,
        organization_id=sample_org_ids["school"],
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )
    contact_person.organization = school_org

    other_contact_person = UserModel(
        id="user-contact-2",
        full_name="Other Contact Person",
        email="other.contact@example.com",
        phone_number="+905551110007",
        password_hash="hashed-password",
        role=ModelUserRole.admin,
        organization_id=sample_org_ids["other"],
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )
    other_contact_person.organization = other_org

    transport_driver = UserModel(
        id="user-driver-1",
        full_name="Transport Driver",
        email="driver@example.com",
        phone_number="+905551110008",
        password_hash="hashed-password",
        role=ModelUserRole.sofor,
        organization_id=sample_org_ids["transport"],
        is_active=True,
        is_email_verified=True,
        created_at=frozen_now,
    )
    transport_driver.organization = transport_org

    return {
        "school_org": school_org,
        "transport_org": transport_org,
        "other_org": other_org,
        "tenant_admin": tenant_admin,
        "super_admin": super_admin,
        "orphan_admin": orphan_admin,
        "inactive_user": inactive_user,
        "managed_user": managed_user,
        "contact_person": contact_person,
        "other_contact_person": other_contact_person,
        "transport_driver": transport_driver,
    }


@pytest.fixture
def fake_redis():
    return SimpleNamespace(
        get=AsyncMock(return_value=None),
        set=AsyncMock(return_value=True),
        delete=AsyncMock(return_value=1),
        delete_pattern=AsyncMock(return_value=1),
        ping=AsyncMock(return_value=True),
    )


@pytest.fixture
def fake_httpx_client():
    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    class FakeAsyncClient:
        def __init__(self, payload):
            self._payload = payload
            self.get = AsyncMock(side_effect=self._get)

        async def _get(self, *args, **kwargs):
            return FakeResponse(self._payload)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def _factory(payload=None):
        return FakeAsyncClient(payload or {"status": "OK", "results": []})

    return _factory


@pytest.fixture
def compiled_sql():
    def _compiled(statement):
        return str(statement.compile(compile_kwargs={"literal_binds": True}))

    return _compiled


@pytest.fixture
def e2e_base_url(monkeypatch):
    return os.getenv("E2E_BASE_URL", "http://localhost:8000")
