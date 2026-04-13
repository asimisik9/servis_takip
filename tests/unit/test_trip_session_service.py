from datetime import datetime, timezone

from app.database import models
from app.database.models.attendance_log import AttendanceLog
from app.services.trip_session_service import TripSessionService


def _attendance_log(log_id: str, status: models.AttendanceStatus, minute: int) -> AttendanceLog:
    return AttendanceLog(
        id=log_id,
        student_id="student-1",
        driver_id="driver-1",
        bus_id="bus-1",
        trip_session_id="session-1",
        status=status,
        latitude=41.0,
        longitude=29.0,
        log_time=datetime(2026, 1, 1, 8, minute, tzinfo=timezone.utc),
        recorded_at=datetime(2026, 1, 1, 8, minute, tzinfo=timezone.utc),
    )


def test_split_logs_for_reopen_reverts_last_completion_for_from_school():
    service = TripSessionService(db=None)  # type: ignore[arg-type]
    logs = [
        _attendance_log("log-bindi", models.AttendanceStatus.bindi, 0),
        _attendance_log("log-indi", models.AttendanceStatus.indi, 5),
    ]

    remaining, reverted = service._split_logs_for_reopen(models.TripType.from_school, logs)

    assert [log.id for log in remaining] == ["log-bindi"]
    assert [log.id for log in reverted] == ["log-indi"]


def test_split_logs_for_reopen_reverts_completion_and_followups_for_to_school():
    service = TripSessionService(db=None)  # type: ignore[arg-type]
    logs = [
        _attendance_log("log-bindi", models.AttendanceStatus.bindi, 0),
        _attendance_log("log-indi", models.AttendanceStatus.indi, 5),
    ]

    remaining, reverted = service._split_logs_for_reopen(models.TripType.to_school, logs)

    assert remaining == []
    assert [log.id for log in reverted] == ["log-bindi", "log-indi"]
