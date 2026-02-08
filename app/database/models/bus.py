# app/models/bus.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
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
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"))
    current_driver_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Multi-tenancy: servis aracı hangi organization'a ait (type=transport_company)
    organization_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # İlişkiler
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="buses"
    )
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

    @property
    def school_name(self) -> str | None:
        return self.school.school_name if self.school else None

    @property
    def driver_name(self) -> str | None:
        return self.current_driver.full_name if self.current_driver else None