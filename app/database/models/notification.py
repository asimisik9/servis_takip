# app/models/notification.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
import enum

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class NotificationStatus(enum.Enum):
    gonderildi = "Gönderildi"
    hatali = "Hatalı"
    beklemede = "Beklemede"


class NotificationType(enum.Enum):
    eve_varis_eta = "eve_varis_eta"           # Eve gelmesine X dakika
    evden_alim_eta = "evden_alim_eta"         # Evden alınmasına X dakika
    okula_varis = "okula_varis"               # Öğrenciler okula vardı
    eve_birakildi = "eve_birakildi"           # Öğrenci evinde indirildi
    genel = "genel"                           # Genel bildirim


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, default="Servis Now")
    message: Mapped[str] = mapped_column(Text)
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType), default=NotificationType.genel
    )
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus))
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # İlişkiler
    recipient: Mapped["User"] = relationship(
        "User", back_populates="notifications"
    )