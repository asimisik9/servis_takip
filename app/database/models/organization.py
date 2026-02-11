# app/database/models/organization.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Enum, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
import enum

from ..database import Base

if TYPE_CHECKING:
    from .user import User
    from .school import School
    from .student import Student
    from .bus import Bus
    from .school_company_contract import SchoolCompanyContract


class OrganizationType(enum.Enum):
    school = "school"
    transport_company = "transport_company"


class Organization(Base):
    __tablename__ = "organizations"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[OrganizationType] = mapped_column(Enum(OrganizationType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # İlişkiler
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="organization"
    )
    schools: Mapped[list["School"]] = relationship(
        "School", back_populates="organization"
    )
    students: Mapped[list["Student"]] = relationship(
        "Student", back_populates="organization"
    )
    buses: Mapped[list["Bus"]] = relationship(
        "Bus", back_populates="organization"
    )
    
    # Sözleşmeler (okul ise company tarafı, şirket ise school tarafı)
    contracts_as_school: Mapped[list["SchoolCompanyContract"]] = relationship(
        "SchoolCompanyContract",
        foreign_keys="SchoolCompanyContract.school_org_id",
        back_populates="school_org"
    )
    contracts_as_company: Mapped[list["SchoolCompanyContract"]] = relationship(
        "SchoolCompanyContract",
        foreign_keys="SchoolCompanyContract.company_org_id",
        back_populates="company_org"
    )
