from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.exceptions import BusinessRuleException
from app.database import models
from app.database.models.attendance_log import AttendanceLog
from app.database.models.bus import Bus
from app.database.models.student_bus_assignment import StudentBusAssignment
from app.database.schemas.attendance_log import AttendanceLogRequest, AttendanceStatus, TripType
from app.services.driver_service import DriverService


pytestmark = pytest.mark.unit


def _build_bus(driver_id: str) -> Bus:
    return Bus(
        id="bus-1",
        plate_number="34 TEST 001",
        capacity=20,
        school_id="school-1",
        current_driver_id=driver_id,
        organization_id="org-transport-1",
    )


def _build_assignment(student_id: str) -> StudentBusAssignment:
    return StudentBusAssignment(
        id="assign-1",
        student_id=student_id,
        bus_id="bus-1",
    )


@pytest.mark.asyncio
async def test_create_attendance_log_rejects_indi_before_bindi(
    mock_db_session, make_execute_result, fake_redis, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"
    state = models.TripStudentState(
        id="state-1",
        trip_session_id="session-1",
        student_id=student_id,
        last_status=None,
    )
    trip_session = SimpleNamespace(id="session-1", trip_type=models.TripType.from_school, last_activity_at=None)

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def resolve_session_for_attendance(self, bus_id, driver_id, requested_trip_type=None):
            return trip_session, models.TripType.from_school

        async def get_or_create_student_state(self, trip_session_id, student_id):
            return state

        @staticmethod
        def should_complete_route(trip_type, attendance_status):
            return False

    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)
    monkeypatch.setattr("app.services.driver_service.redis_manager", fake_redis)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=_build_assignment(student_id)),
    ]

    service = DriverService(mock_db_session)

    with pytest.raises(BusinessRuleException) as exc:
        await service.create_attendance_log(
            driver_id=driver_id,
            attendance=AttendanceLogRequest(
                student_id=student_id,
                status=AttendanceStatus.indi,
                latitude=41.0,
                longitude=29.0,
                log_time=datetime.now(timezone.utc),
                trip_type=TripType.from_school,
            ),
        )

    assert "before 'bindi'" in exc.value.message
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_attendance_log_returns_previous_log_for_duplicate_status(
    mock_db_session, make_execute_result, fake_redis, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"
    existing_log = AttendanceLog(
        id="log-1",
        student_id=student_id,
        driver_id=driver_id,
        bus_id="bus-1",
        status=models.AttendanceStatus.bindi,
        latitude=41.0,
        longitude=29.0,
        log_time=datetime.now(timezone.utc),
    )
    state = models.TripStudentState(
        id="state-1",
        trip_session_id="session-1",
        student_id=student_id,
        last_status=models.AttendanceStatus.bindi,
        last_log_id=existing_log.id,
    )
    state.last_log = existing_log
    trip_session = SimpleNamespace(id="session-1", trip_type=models.TripType.to_school, last_activity_at=None)

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def resolve_session_for_attendance(self, bus_id, driver_id, requested_trip_type=None):
            return trip_session, models.TripType.to_school

        async def get_or_create_student_state(self, trip_session_id, student_id):
            return state

        @staticmethod
        def should_complete_route(trip_type, attendance_status):
            return True

    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)
    monkeypatch.setattr("app.services.driver_service.redis_manager", fake_redis)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=None),
        make_execute_result(scalar_one_or_none=_build_assignment(student_id)),
    ]

    service = DriverService(mock_db_session)
    result = await service.create_attendance_log(
        driver_id=driver_id,
        attendance=AttendanceLogRequest(
            student_id=student_id,
            status=AttendanceStatus.bindi,
            latitude=41.0,
            longitude=29.0,
            log_time=datetime.now(timezone.utc),
            trip_type=TripType.to_school,
        ),
    )

    assert result is existing_log
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_attendance_log_marks_route_complete_for_to_school_bindi(
    mock_db_session, make_execute_result, fake_redis, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"
    state = models.TripStudentState(
        id="state-1",
        trip_session_id="session-1",
        student_id=student_id,
        last_status=None,
    )
    trip_session = SimpleNamespace(id="session-1", trip_type=models.TripType.to_school, last_activity_at=None)

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def resolve_session_for_attendance(self, bus_id, driver_id, requested_trip_type=None):
            return trip_session, models.TripType.to_school

        async def get_or_create_student_state(self, trip_session_id, student_id):
            return state

        @staticmethod
        def should_complete_route(trip_type, attendance_status):
            return True

    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)
    monkeypatch.setattr("app.services.driver_service.redis_manager", fake_redis)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=_build_assignment(student_id)),
    ]

    service = DriverService(mock_db_session)
    result = await service.create_attendance_log(
        driver_id=driver_id,
        attendance=AttendanceLogRequest(
            student_id=student_id,
            status=AttendanceStatus.bindi,
            latitude=41.0,
            longitude=29.0,
            log_time=datetime.now(timezone.utc),
            trip_type=TripType.to_school,
            idempotency_key="attendance-student-1-bindi",
        ),
    )

    assert isinstance(result, AttendanceLog)
    assert result.trip_session_id == "session-1"
    assert result.idempotency_key == "attendance-student-1-bindi"
    assert state.last_status == models.AttendanceStatus.bindi
    assert state.route_completed_at is not None
    assert state.last_log_id == result.id
    mock_db_session.flush.assert_awaited_once()
    mock_db_session.commit.assert_awaited_once()
    fake_redis.set.assert_awaited_once_with("bus:bus-1:trip_type", "to_school", ex=3600)


@pytest.mark.asyncio
async def test_create_attendance_log_returns_existing_row_for_matching_idempotency_key(
    mock_db_session, make_execute_result, fake_redis, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"
    existing_log = AttendanceLog(
        id="log-1",
        student_id=student_id,
        driver_id=driver_id,
        bus_id="bus-1",
        status=models.AttendanceStatus.bindi,
        latitude=41.0,
        longitude=29.0,
        log_time=datetime.now(timezone.utc),
        idempotency_key="attendance-student-1-bindi",
    )

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def resolve_session_for_attendance(self, bus_id, driver_id, requested_trip_type=None):
            return SimpleNamespace(id="session-1"), models.TripType.to_school

        async def get_or_create_student_state(self, trip_session_id, student_id):
            raise AssertionError("state should not be loaded when idempotency key already exists")

        @staticmethod
        def should_complete_route(trip_type, attendance_status):
            return True

    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)
    monkeypatch.setattr("app.services.driver_service.redis_manager", fake_redis)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=existing_log),
    ]

    service = DriverService(mock_db_session)
    result = await service.create_attendance_log(
        driver_id=driver_id,
        attendance=AttendanceLogRequest(
            student_id=student_id,
            status=AttendanceStatus.bindi,
            latitude=41.0,
            longitude=29.0,
            log_time=datetime.now(timezone.utc),
            trip_type=TripType.to_school,
            idempotency_key="attendance-student-1-bindi",
        ),
    )

    assert result is existing_log
    mock_db_session.add.assert_not_called()
    mock_db_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reopen_student_route_progress_commits_when_attendance_state_reopens(
    mock_db_session, make_execute_result, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"

    class FakeRouteProgressService:
        async def remove_visited(self, bus_id, trip_type, student_id):
            return False

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def reopen_student_route(self, **kwargs):
            return True

    monkeypatch.setattr("app.services.driver_service.RouteProgressService", FakeRouteProgressService)
    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=_build_assignment(student_id)),
    ]

    service = DriverService(mock_db_session)
    result = await service.reopen_student_route_progress(
        driver_id=driver_id,
        student_id=student_id,
        trip_type="from_school",
    )

    assert result is True
    mock_db_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reopen_student_route_progress_skips_commit_for_manual_only_reopen(
    mock_db_session, make_execute_result, monkeypatch
):
    driver_id = "driver-1"
    student_id = "student-1"

    class FakeRouteProgressService:
        async def remove_visited(self, bus_id, trip_type, student_id):
            return True

    class FakeTripSessionService:
        def __init__(self, db):
            self.db = db

        async def reopen_student_route(self, **kwargs):
            return False

    monkeypatch.setattr("app.services.driver_service.RouteProgressService", FakeRouteProgressService)
    monkeypatch.setattr("app.services.driver_service.TripSessionService", FakeTripSessionService)

    mock_db_session.execute.side_effect = [
        make_execute_result(scalar_one_or_none=_build_bus(driver_id)),
        make_execute_result(scalar_one_or_none=_build_assignment(student_id)),
    ]

    service = DriverService(mock_db_session)
    result = await service.reopen_student_route_progress(
        driver_id=driver_id,
        student_id=student_id,
        trip_type="to_school",
    )

    assert result is True
    mock_db_session.commit.assert_not_awaited()
