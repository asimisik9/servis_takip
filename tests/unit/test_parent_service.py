from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.database.models.attendance_log import AttendanceLog, AttendanceStatus
from app.services.parent_service import ParentService


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_get_student_attendance_history_filters_reverted_logs_and_localizes_timeline(
    mock_db_session,
    make_execute_result,
):
    active_log = AttendanceLog(
        id="log-1",
        student_id="student-1",
        driver_id="driver-1",
        bus_id="bus-1",
        status=AttendanceStatus.bindi,
        latitude=38.4818,
        longitude=28.1394,
        log_time=datetime(2026, 1, 1, 6, 30),
    )
    service = ParentService(mock_db_session)
    service._ensure_parent_student_relation = AsyncMock()
    mock_db_session.execute.return_value = make_execute_result(all_items=[active_log])

    result = await service.get_student_attendance_history(
        parent_id="parent-1",
        student_id="student-1",
        filter_date=date(2026, 1, 1),
        timezone_name="Europe/Istanbul",
    )

    statement = mock_db_session.execute.await_args.args[0]
    compiled = statement.compile()

    assert "reverted_at IS NULL" in str(statement)
    assert compiled.params["log_time_1"] == datetime(2025, 12, 31, 21, 0)
    assert compiled.params["log_time_2"] == datetime(2026, 1, 1, 21, 0)
    assert len(result) == 1
    assert result[0].id == "log-1"
    assert result[0].status.value == "bindi"
    assert result[0].log_time.isoformat() == "2026-01-01T09:30:00+03:00"


@pytest.mark.asyncio
async def test_get_student_attendance_history_rejects_invalid_timezone(
    mock_db_session,
):
    service = ParentService(mock_db_session)
    service._ensure_parent_student_relation = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        await service.get_student_attendance_history(
            parent_id="parent-1",
            student_id="student-1",
            timezone_name="Mars/Phobos",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid timezone"
    mock_db_session.execute.assert_not_awaited()
