from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.database.schemas.user import UserCreate, UserRole, UserUpdate
from app.services.user_service import UserService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_tenant_admin_cannot_create_super_admin(
    mock_db_session, make_execute_result, sample_org_ids
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=None),
    ]
    service = UserService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.create_user(
            UserCreate(
                full_name="New Super Admin",
                email="super@example.com",
                phone_number="+905551112200",
                password="StrongPass1",
                role=UserRole.super_admin,
            ),
            current_user_org_id=sample_org_ids["school"],
        )

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Tenant admins cannot create super_admin users"


@pytest.mark.asyncio
async def test_super_admin_user_cannot_be_bound_to_organization(
    mock_db_session, make_execute_result, sample_org_ids
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=None),
    ]
    service = UserService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await service.create_user(
            UserCreate(
                full_name="Bound Super Admin",
                email="bound.super@example.com",
                phone_number="+905551112201",
                password="StrongPass1",
                role=UserRole.super_admin,
                organization_id=sample_org_ids["school"],
            ),
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "super_admin users cannot be bound to an organization"


@pytest.mark.asyncio
async def test_tenant_bound_roles_require_organization(mock_db_session, make_execute_result):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=None),
    ]
    service = UserService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.create_user(
            UserCreate(
                full_name="Tenant Admin",
                email="tenantless@example.com",
                phone_number="+905551112202",
                password="StrongPass1",
                role=UserRole.admin,
            ),
        )

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "admin users must belong to an organization"


@pytest.mark.asyncio
async def test_tenant_admin_create_forces_current_organization(
    mock_db_session, make_execute_result, sample_org_ids, sample_users
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=None),
    ]
    service = UserService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()
    service.get_user_by_id = AsyncMock(return_value=sample_users["managed_user"])

    await service.create_user(
        UserCreate(
            full_name="Tenant Scoped User",
            email="tenant.scoped@example.com",
            phone_number="+905551112203",
            password="StrongPass1",
            role=UserRole.veli,
            organization_id=sample_org_ids["other"],
        ),
        current_user_org_id=sample_org_ids["school"],
    )

    created_user = mock_db_session.add.call_args.args[0]
    assert created_user.organization_id == sample_org_ids["school"]
    service._ensure_organization_exists.assert_awaited_once_with(sample_org_ids["school"])


@pytest.mark.asyncio
async def test_tenant_admin_update_forces_current_organization(
    mock_db_session, make_execute_result, sample_org_ids, sample_users
):
    existing_user = sample_users["managed_user"]
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=existing_user)

    service = UserService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()
    service.get_user_by_id = AsyncMock(return_value=existing_user)

    result = await service.update_user(
        existing_user.id,
        UserUpdate(full_name="Updated Name", organization_id=sample_org_ids["other"]),
        current_user_org_id=sample_org_ids["school"],
    )

    assert result is existing_user
    assert existing_user.organization_id == sample_org_ids["school"]
    assert existing_user.full_name == "Updated Name"
    service._ensure_organization_exists.assert_awaited_once_with(sample_org_ids["school"])


@pytest.mark.asyncio
async def test_get_users_applies_tenant_filter(
    mock_db_session, make_execute_result, sample_org_ids, sample_users, compiled_sql
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar=1),
        make_execute_result(all_items=[sample_users["managed_user"]]),
    ]
    service = UserService(mock_db_session)

    users, total = await service.get_users(
        skip=0,
        limit=20,
        current_user_org_id=sample_org_ids["school"],
        organization_filter=sample_org_ids["other"],
    )

    assert total == 1
    assert users == [sample_users["managed_user"]]
    data_query = mock_db_session.execute.await_args_list[1].args[0]
    assert sample_org_ids["school"] in compiled_sql(data_query)
    assert sample_org_ids["other"] not in compiled_sql(data_query)


@pytest.mark.asyncio
async def test_delete_user_prevents_self_delete(mock_db_session):
    service = UserService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.delete_user("user-1", current_user_id="user-1", current_user_org_id="org-school-1")

    assert exc.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc.value.detail == "Admin cannot delete themselves"
    mock_db_session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_user_rejects_contact_person_deactivation(
    mock_db_session, make_execute_result, sample_users, sample_org_ids
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=sample_users["managed_user"]),
        make_execute_result(scalar=2),
    ]
    service = UserService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.delete_user(
            sample_users["managed_user"].id,
            current_user_id=sample_users["tenant_admin"].id,
            current_user_org_id=sample_org_ids["school"],
        )

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "Cannot delete user" in exc.value.detail
