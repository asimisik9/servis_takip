# app/models/user.py

from sqlalchemy import String, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from typing import TYPE_CHECKING
from ..database import Base

if TYPE_CHECKING:
    from .school import School
    from .bus import Bus
    from .parent_student_relation import ParentStudentRelation
    from .attendance_log import AttendanceLog
    from .notification import Notification

class UserRole(enum.Enum):
    veli = "veli"
    sofor = "sofor"
    admin = "admin"
    
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.veli)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # İlişkiler
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
    
