# app/models/parent_student_relation.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User
    from .student import Student


class ParentStudentRelation(Base):
    __tablename__ = "parent_student_relations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    parent_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))

    # İlişkiler
    parent: Mapped["User"] = relationship(
        "User", back_populates="parent_relations"
    )
    student: Mapped["Student"] = relationship(
        "Student", back_populates="parent_relations"
    )