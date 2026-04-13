from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.database.models.bus import Bus
from app.database.models.organization import Organization, OrganizationType
from app.database.models.school import School
from app.database.models.user import User as UserModel, UserRole as ModelUserRole
from app.database.schemas.school import SchoolCreate, SchoolUpdate
from app.services.school_service import SchoolService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_create_school_requires_school_type_organization(
    mock_db_session, make_execute_result, sample_org_ids, sample_users, frozen_now
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=sample_users["contact_person"]),
        make_execute_result(
            scalar_one_or_none=Organization(
                id=sample_org_ids["transport"],
                name="Transport Org",
                type=OrganizationType.transport_company,
                is_active=True,
                created_at=frozen_now,
            )
        ),
    ]
    service = SchoolService(mock_db_session)
    service._geocode_address = AsyncMock(return_value=(None, None))

    with pytest.raises(HTTPException) as exc:
        await service.create_school(
            SchoolCreate(
                school_name="New School",
                school_address="Address",
                contact_person_id=sample_users["contact_person"].id,
                organization_id=sample_org_ids["transport"],
            ),
            current_user_org_id=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Organization must be of type 'school'"


@pytest.mark.asyncio
async def test_update_school_requires_school_type_organization(
    mock_db_session, make_execute_result, sample_org_ids, frozen_now
):
    existing_school = School(
        id="school-1",
        school_name="Existing School",
        school_address="Address",
        contact_person_id="user-contact-1",
        organization_id=sample_org_ids["school"],
    )
    mock_db_session.execute.return_value = make_execute_result(
        scalar_one_or_none=Organization(
            id=sample_org_ids["transport"],
            name="Transport Org",
            type=OrganizationType.transport_company,
            is_active=True,
            created_at=frozen_now,
        )
    )
    service = SchoolService(mock_db_session)
    service.get_school_by_id = AsyncMock(return_value=existing_school)

    with pytest.raises(HTTPException) as exc:
        await service.update_school(
            existing_school.id,
            SchoolUpdate(organization_id=sample_org_ids["transport"]),
            current_user_org_id=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Organization must be of type 'school'"


@pytest.mark.asyncio
async def test_tenant_admin_cannot_override_school_organization(
    mock_db_session, make_execute_result, sample_org_ids, sample_users
):
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=sample_users["contact_person"]),
    ]
    service = SchoolService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.create_school(
            SchoolCreate(
                school_name="Tenant School",
                school_address="Address",
                contact_person_id=sample_users["contact_person"].id,
                organization_id=sample_org_ids["other"],
            ),
            current_user_org_id=sample_org_ids["school"],
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Cannot override tenant organization"


@pytest.mark.asyncio
async def test_update_school_rejects_contact_person_from_other_organization(
    mock_db_session, make_execute_result, sample_org_ids, sample_users
):
    existing_school = School(
        id="school-1",
        school_name="Existing School",
        school_address="Address",
        contact_person_id=sample_users["contact_person"].id,
        organization_id=sample_org_ids["school"],
    )
    mock_db_session.execute.return_value = make_execute_result(
        scalar_one_or_none=sample_users["other_contact_person"]
    )
    service = SchoolService(mock_db_session)
    service.get_school_by_id = AsyncMock(return_value=existing_school)
    service._validate_school_organization = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await service.update_school(
            existing_school.id,
            SchoolUpdate(contact_person_id=sample_users["other_contact_person"].id),
            current_user_org_id=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Contact person not found or access denied"


@pytest.mark.asyncio
async def test_delete_school_rejects_when_students_are_linked(
    mock_db_session, make_execute_result, sample_org_ids
):
    existing_school = School(
        id="school-1",
        school_name="Existing School",
        school_address="Address",
        contact_person_id="user-contact-1",
        organization_id=sample_org_ids["school"],
    )
    mock_db_session.execute.return_value = make_execute_result(scalar=2)
    service = SchoolService(mock_db_session)
    service.get_school_by_id = AsyncMock(return_value=existing_school)

    with pytest.raises(HTTPException) as exc:
        await service.delete_school(existing_school.id, current_user_org_id=sample_org_ids["school"])

    assert exc.value.status_code == 409
    assert "student(s) belong to it" in exc.value.detail


@pytest.mark.asyncio
async def test_delete_school_rejects_when_buses_are_linked(
    mock_db_session, make_execute_result, sample_org_ids
):
    existing_school = School(
        id="school-1",
        school_name="Existing School",
        school_address="Address",
        contact_person_id="user-contact-1",
        organization_id=sample_org_ids["school"],
    )
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar=0),
        make_execute_result(scalar=1),
    ]
    service = SchoolService(mock_db_session)
    service.get_school_by_id = AsyncMock(return_value=existing_school)

    with pytest.raises(HTTPException) as exc:
        await service.delete_school(existing_school.id, current_user_org_id=sample_org_ids["school"])

    assert exc.value.status_code == 409
    assert "bus(es) belong to it" in exc.value.detail
