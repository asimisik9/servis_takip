# app/models/bus.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .school import School
    from .user import User
    from .student_bus_assignment import StudentBusAssignment
    from .attendance_log import AttendanceLog
    from .bus_location import BusLocation


class Bus(Base):
    __tablename__ = "buses"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    plate_number: Mapped[str] = mapped_column(String, unique=True)
    capacity: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    current_driver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    # İlişkiler
    school: Mapped["School"] = relationship(
        "School", back_populates="buses"
    )
    current_driver: Mapped["User"] = relationship(
        "User", back_populates="buses_driver"
    )
    student_assignments: Mapped[list["StudentBusAssignment"]] = relationship(
        "StudentBusAssignment", back_populates="bus"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="bus"
    )
    bus_locations: Mapped[list["BusLocation"]] = relationship(
        "BusLocation", back_populates="bus"
    )