from __future__ import annotations

from datetime import date, datetime, timezone
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .attendance_log import AttendanceLog
    from .bus import Bus
    from .trip_student_state import TripStudentState
    from .user import User


class TripType(enum.Enum):
    to_school = "to_school"
    from_school = "from_school"


class TripSession(Base):
    __tablename__ = "trip_sessions"
    __table_args__ = (
        UniqueConstraint("bus_id", "trip_type", "service_date", name="uq_trip_session_bus_type_date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id", ondelete="CASCADE"), index=True)
    driver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    trip_type: Mapped[TripType] = mapped_column(Enum(TripType))
    service_date: Mapped[date] = mapped_column(Date, index=True, default=date.today)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    bus: Mapped["Bus"] = relationship("Bus")
    driver: Mapped["User | None"] = relationship("User")
    student_states: Mapped[list["TripStudentState"]] = relationship(
        "TripStudentState",
        back_populates="trip_session",
        cascade="all, delete-orphan",
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog",
        back_populates="trip_session",
    )
