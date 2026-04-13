from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Enum, DateTime, ForeignKey, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..database import Base

if TYPE_CHECKING:
    from .student import Student
    from .user import User
    from .bus import Bus
    from .trip_session import TripSession


class AttendanceStatus(enum.Enum):
    indi = "indi"
    bindi = "bindi"

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    driver_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id", ondelete="RESTRICT"))
    trip_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("trip_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus))
    latitude: Mapped[float] = mapped_column(DECIMAL(10, 8))
    longitude: Mapped[float] = mapped_column(DECIMAL(11, 8))
    log_time: Mapped[DateTime] = mapped_column(DateTime)
    recorded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    reverted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reverted_by_driver_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # İlişkiler
    student: Mapped["Student"] = relationship(
        "Student", back_populates="attendance_logs"
    )
    driver: Mapped["User"] = relationship(
        "User",
        back_populates="attendance_logs",
        foreign_keys=[driver_id],
    )
    reverted_by_driver: Mapped["User | None"] = relationship(
        "User",
        back_populates="reverted_attendance_logs",
        foreign_keys=[reverted_by_driver_id],
    )
    bus: Mapped["Bus"] = relationship(
        "Bus", back_populates="attendance_logs"
    )
    trip_session: Mapped["TripSession | None"] = relationship(
        "TripSession", back_populates="attendance_logs"
    )
