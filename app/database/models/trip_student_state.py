from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base
from .attendance_log import AttendanceStatus

if TYPE_CHECKING:
    from .attendance_log import AttendanceLog
    from .student import Student
    from .trip_session import TripSession


class TripStudentState(Base):
    __tablename__ = "trip_student_states"
    __table_args__ = (
        UniqueConstraint("trip_session_id", "student_id", name="uq_trip_session_student"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    trip_session_id: Mapped[str] = mapped_column(ForeignKey("trip_sessions.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    last_status: Mapped[AttendanceStatus | None] = mapped_column(Enum(AttendanceStatus), nullable=True)
    last_log_id: Mapped[str | None] = mapped_column(
        ForeignKey("attendance_logs.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    route_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trip_session: Mapped["TripSession"] = relationship("TripSession", back_populates="student_states")
    student: Mapped["Student"] = relationship("Student")
    last_log: Mapped["AttendanceLog | None"] = relationship("AttendanceLog")
