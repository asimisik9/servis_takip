# app/database/models/school_company_contract.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Date, Boolean, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime, timezone

from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization


class SchoolCompanyContract(Base):
    """
    Okul-Servis şirketi sözleşmesi.
    Bir okul birden fazla servis şirketiyle çalışabilir.
    Bir servis şirketi birden fazla okula hizmet verebilir.
    """
    __tablename__ = "school_company_contracts"
    __table_args__ = (
        UniqueConstraint('school_org_id', 'company_org_id', name='uq_school_company_contract'),
    )
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    school_org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    company_org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    
    # İlişkiler
    school_org: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[school_org_id],
        back_populates="contracts_as_school"
    )
    company_org: Mapped["Organization"] = relationship(
        "Organization",
        foreign_keys=[company_org_id],
        back_populates="contracts_as_company"
    )
