# app/models/school.py
from sqlalchemy import String, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
    from .user import User
    from .student import Student
    from .bus import Bus

class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_name: Mapped[str] = mapped_column(String)
    school_address: Mapped[str] = mapped_column(String)
    contact_person_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Multi-tenancy: okul hangi organization'a ait (type=school)
    organization_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # İlişkiler
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="schools"
    )
    contact_person: Mapped["User"] = relationship(
        "User", back_populates="schools_contact_person"
    )
    students: Mapped[list["Student"]] = relationship(
        "Student", back_populates="school"
    )
    buses: Mapped[list["Bus"]] = relationship(
        "Bus", back_populates="school"
    )

    @property
    def contact_person_name(self) -> str | None:
        return self.contact_person.full_name if self.contact_person else None