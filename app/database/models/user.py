# app/models/user.py

from sqlalchemy import String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
import enum
from typing import TYPE_CHECKING, Optional
from ..database import Base

if TYPE_CHECKING:
    from .organization import Organization
    from .school import School
    from .bus import Bus
    from .parent_student_relation import ParentStudentRelation
    from .attendance_log import AttendanceLog
    from .notification import Notification
    from .password_reset_token import PasswordResetToken
    from .email_verification_token import EmailVerificationToken

class UserRole(enum.Enum):
    veli = "veli"
    sofor = "sofor"
    admin = "admin"  # Organizasyon admin'i (okul veya servis şirketi yöneticisi)
    super_admin = "super_admin"  # Platform yöneticisi (tüm organizasyonları yönetebilir)
    
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.veli)
    fcm_token: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Multi-tenancy: NULL = super-admin (platform yöneticisi), değer = tenant kullanıcısı
    organization_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=lambda: datetime.now(timezone.utc))

    # İlişkiler
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="users"
    )
    schools_contact_person: Mapped[list["School"]] = relationship(
        "School", back_populates="contact_person"
    )
    buses_driver: Mapped[list["Bus"]] = relationship(
        "Bus", back_populates="current_driver"
    )
    parent_relations: Mapped[list["ParentStudentRelation"]] = relationship(
        "ParentStudentRelation", back_populates="parent"
    )
    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog", back_populates="driver"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="recipient"
    )
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens: Mapped[list["EmailVerificationToken"]] = relationship(
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def organization_name(self) -> str | None:
        """Computed property: organization name from relationship."""
        return self.organization.name if self.organization else None
    
