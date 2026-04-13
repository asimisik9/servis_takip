from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.redis import redis_manager
from app.database.models.attendance_log import AttendanceLog
from app.database.models.organization import Organization, OrganizationType
from app.database.models.school import School
from app.database.models.student import Student
from app.database.models.student_bus_assignment import StudentBusAssignment
from app.database.schemas.student import StudentCreate, StudentUpdate
from app.services.student_service import StudentService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_create_student_requires_organization_id(mock_db_session, make_execute_result):
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    service = StudentService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.create_student(
            StudentCreate(
                full_name="Student One",
                student_number="STD-001",
                address="Sample Address",
            ),
            current_user_org_id=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "organization_id is required for student creation"


@pytest.mark.asyncio
async def test_create_student_rejects_school_from_other_org_for_school_tenant(
    mock_db_session, make_execute_result, sample_org_ids, frozen_now
):
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    mock_db_session.get.side_effect = [
        School(
            id="school-1",
            school_name="Other School",
            school_address="Address",
            contact_person_id="user-contact-2",
            organization_id=sample_org_ids["other"],
        ),
        Organization(
            id=sample_org_ids["school"],
            name="School Org",
            type=OrganizationType.school,
            is_active=True,
            created_at=frozen_now,
        ),
    ]
    service = StudentService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await service.create_student(
            StudentCreate(
                full_name="Student One",
                student_number="STD-001",
                school_id="school-1",
                organization_id=sample_org_ids["school"],
            ),
            current_user_org_id=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "School does not belong to student's organization"


@pytest.mark.asyncio
async def test_create_student_allows_cross_org_school_for_transport_company(
    mock_db_session, make_execute_result, sample_org_ids, frozen_now
):
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=None)
    mock_db_session.get.side_effect = [
        School(
            id="school-1",
            school_name="School",
            school_address="Address",
            contact_person_id="user-contact-1",
            organization_id=sample_org_ids["other"],
        ),
        Organization(
            id=sample_org_ids["transport"],
            name="Transport Org",
            type=OrganizationType.transport_company,
            is_active=True,
            created_at=frozen_now,
        ),
    ]
    service = StudentService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()
    service._geocode_address = AsyncMock(return_value=(None, None))
    service.get_student_by_id = AsyncMock(
        return_value=Student(
            id="student-1",
            full_name="Student One",
            student_number="STD-001",
            school_id="school-1",
            organization_id=sample_org_ids["transport"],
        )
    )

    result = await service.create_student(
        StudentCreate(
            full_name="Student One",
            student_number="STD-001",
            school_id="school-1",
            organization_id=sample_org_ids["transport"],
        ),
        current_user_org_id=None,
    )

    created_student = mock_db_session.add.call_args.args[0]
    assert result.organization_id == sample_org_ids["transport"]
    assert created_student.school_id == "school-1"


@pytest.mark.asyncio
async def test_update_student_invalidates_route_cache_when_address_changes(
    mock_db_session, make_execute_result, sample_org_ids
):
    existing_student = Student(
        id="student-1",
        full_name="Student One",
        student_number="STD-001",
        school_id=None,
        organization_id=sample_org_ids["school"],
        address="Old Address",
    )
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=existing_student)

    service = StudentService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()
    service._geocode_address = AsyncMock(return_value=(38.5, 27.1))
    service._invalidate_route_caches_for_student = AsyncMock()
    service.get_student_by_id = AsyncMock(return_value=existing_student)

    await service.update_student(
        existing_student.id,
        StudentUpdate(address="New Address"),
        current_user_org_id=sample_org_ids["school"],
    )

    assert existing_student.address == "New Address"
    assert existing_student.latitude == 38.5
    assert existing_student.longitude == 27.1
    service._invalidate_route_caches_for_student.assert_awaited_once_with(existing_student.id)


@pytest.mark.asyncio
async def test_update_student_skips_route_cache_invalidation_when_address_is_unchanged(
    mock_db_session, make_execute_result, sample_org_ids
):
    existing_student = Student(
        id="student-1",
        full_name="Student One",
        student_number="STD-001",
        school_id=None,
        organization_id=sample_org_ids["school"],
        address="Same Address",
    )
    mock_db_session.execute.return_value = make_execute_result(scalar_one_or_none=existing_student)

    service = StudentService(mock_db_session)
    service._ensure_organization_exists = AsyncMock()
    service._geocode_address = AsyncMock()
    service._invalidate_route_caches_for_student = AsyncMock()
    service.get_student_by_id = AsyncMock(return_value=existing_student)

    await service.update_student(
        existing_student.id,
        StudentUpdate(address="Same Address"),
        current_user_org_id=sample_org_ids["school"],
    )

    service._geocode_address.assert_not_awaited()
    service._invalidate_route_caches_for_student.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_student_rejects_when_attendance_logs_exist(
    mock_db_session, make_execute_result, sample_org_ids
):
    existing_student = Student(
        id="student-1",
        full_name="Student One",
        student_number="STD-001",
        school_id=None,
        organization_id=sample_org_ids["school"],
    )
    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=existing_student),
        make_execute_result(scalar=1),
    ]
    service = StudentService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.delete_student(existing_student.id, current_user_org_id=sample_org_ids["school"])

    assert exc.value.status_code == 409
    assert "attendance log" in exc.value.detail


@pytest.mark.asyncio
async def test_invalidate_route_caches_deletes_patterns_for_all_assigned_buses(
    mock_db_session, make_execute_result, fake_redis
):
    assignments = [
        StudentBusAssignment(id="assign-1", student_id="student-1", bus_id="bus-1"),
        StudentBusAssignment(id="assign-2", student_id="student-1", bus_id="bus-2"),
    ]
    mock_db_session.execute.return_value = make_execute_result(all_items=assignments)
    service = StudentService(mock_db_session)

    original_delete_pattern = redis_manager.delete_pattern
    redis_manager.delete_pattern = fake_redis.delete_pattern
    try:
        await service._invalidate_route_caches_for_student("student-1")
    finally:
        redis_manager.delete_pattern = original_delete_pattern

    fake_redis.delete_pattern.assert_any_await("route:bus-1:*")
    fake_redis.delete_pattern.assert_any_await("route:bus-2:*")
