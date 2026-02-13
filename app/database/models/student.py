# app/models/student.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional
from sqlalchemy import String, ForeignKey, DateTime, Float, inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from ..database import Base

if TYPE_CHECKING:
    from .school import School
    from .organization import Organization
    from .parent_student_relation import ParentStudentRelation
    from .student_bus_assignment import StudentBusAssignment
    from .attendance_log import AttendanceLog


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    student_number: Mapped[str] = mapped_column(String, unique=True)
    school_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("schools.id", ondelete="RESTRICT"),
        nullable=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # İlişkiler
    school: Mapped[Optional["School"]] = relationship(
        "School", back_populates="students"
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="students"
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

    def _get_loaded_relation(self, relation_name: str):
        """
        Return relation object only if already loaded.
        Prevents accidental async lazy-load during response serialization.
        """
        state = sa_inspect(self)
        if relation_name in state.unloaded or relation_name in state.expired_attributes:
            return None
        return getattr(self, relation_name, None)

    @property
    def school_name(self) -> str | None:
        school = self._get_loaded_relation("school")
        return school.school_name if school else None

    @property
    def organization_name(self) -> str | None:
        organization = self._get_loaded_relation("organization")
        return organization.name if organization else None
