# app/models/school.py
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_name: Mapped[str] = mapped_column(String)
    school_address: Mapped[str] = mapped_column(String)
    contact_person_id: Mapped[str] = mapped_column(ForeignKey("users.id"))

    # İlişkiler
    contact_person: Mapped["User"] = relationship(
        "User", back_populates="schools_contact_person"
    )
    students: Mapped[list["Student"]] = relationship(
        "Student", back_populates="school"
    )
    buses: Mapped[list["Bus"]] = relationship(
        "Bus", back_populates="school"
    )