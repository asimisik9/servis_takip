from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.database.models.bus import Bus
from app.database.models.student import Student
from app.database.models.student_bus_assignment import StudentBusAssignment
from app.services.assignment_service import AssignmentService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_assign_bus_to_student_rejects_when_student_already_assigned_to_another_bus(
    mock_db_session, make_execute_result, sample_org_ids
):
    student = Student(
        id="student-1",
        full_name="Student One",
        student_number="STD-001",
        school_id="school-1",
        organization_id=sample_org_ids["transport"],
        created_at=datetime.now(timezone.utc),
    )
    bus = Bus(
        id="bus-2",
        plate_number="34 TEST 002",
        capacity=20,
        school_id="school-1",
        organization_id=sample_org_ids["transport"],
    )
    existing_assignment = StudentBusAssignment(
        id="assign-1",
        student_id=student.id,
        bus_id="bus-1",
    )

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=student),
        make_execute_result(scalar_one_or_none=bus),
        make_execute_result(scalar_one_or_none=existing_assignment),
    ]

    service = AssignmentService(mock_db_session)

    with pytest.raises(HTTPException) as exc:
        await service.assign_bus_to_student(
            student_id=student.id,
            bus_id=bus.id,
            current_user_org_id=sample_org_ids["transport"],
        )

    assert exc.value.status_code == 409
    assert "already assigned to another bus" in exc.value.detail
    mock_db_session.commit.assert_not_awaited()

