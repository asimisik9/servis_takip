# app/models/student_bus_assignment.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .bus import Bus
    from .student import Student


class StudentBusAssignment(Base):
    __tablename__ = "student_bus_assignments"
    __table_args__ = (
        UniqueConstraint('bus_id', 'student_id', name='uq_bus_student'),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    bus_id: Mapped[str] = mapped_column(ForeignKey("buses.id", ondelete="CASCADE"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))

    # İlişkiler
    bus: Mapped["Bus"] = relationship(
        "Bus", back_populates="student_assignments"
    )
    student: Mapped["Student"] = relationship(
        "Student", back_populates="bus_assignments"
    )