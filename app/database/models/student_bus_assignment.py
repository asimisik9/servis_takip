# app/models/student_bus_assignment.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .bus import Bus
    from .student import Student


class StudentBusAssignment(Base):
    __tablename__ = "student_bus_assignments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))

    # İlişkiler
    bus: Mapped["Bus"] = relationship(
        "Bus", back_populates="student_assignments"
    )
    student: Mapped["Student"] = relationship(
        "Student", back_populates="bus_assignments"
    )