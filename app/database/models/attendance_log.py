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


class AttendanceStatus(enum.Enum):
    indi = "İndi"
    bindi = "Bindi"

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    driver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"))
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus))
    latitude: Mapped[float] = mapped_column(DECIMAL(10, 8))
    longitude: Mapped[float] = mapped_column(DECIMAL(11, 8))
    log_time: Mapped[DateTime] = mapped_column(DateTime)

    # İlişkiler
    student: Mapped["Student"] = relationship(
        "Student", back_populates="attendance_logs"
    )
    driver: Mapped["User"] = relationship(
        "User", back_populates="attendance_logs"
    )
    bus: Mapped["Bus"] = relationship(
        "Bus", back_populates="attendance_logs"
    )