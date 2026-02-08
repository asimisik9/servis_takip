# app/models/student.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from ..database import Base

if TYPE_CHECKING:
    from .school import School
    from .parent_student_relation import ParentStudentRelation
    from .student_bus_assignment import StudentBusAssignment
    from .attendance_log import AttendanceLog


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    student_number: Mapped[str] = mapped_column(String, unique=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="RESTRICT"))
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # İlişkiler
    school: Mapped["School"] = relationship(
        "School", back_populates="students"
    )
    parent_relations: Mapped[list["ParentStudentRelation"]] = relationship(
        "ParentStudentRelation", back_populates="student"
    )
    bus_assignments: Mapped[list["StudentBusAssignment"]] = relationship(
        "StudentBusAssignment", back_populates="student"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="student"
    )

    @property
    def school_name(self) -> str | None:
        return self.school.school_name if self.school else None