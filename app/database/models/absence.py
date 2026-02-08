from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Date, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, timezone

from ..database import Base

if TYPE_CHECKING:
    from .student import Student
    from .user import User


class Absence(Base):
    __tablename__ = "absences"
    __table_args__ = (
        UniqueConstraint('student_id', 'absence_date', name='uq_student_absence_date'),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    parent_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    absence_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relations
    student: Mapped["Student"] = relationship("Student")
    parent: Mapped["User"] = relationship("User")
