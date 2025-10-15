# app/models/notification.py
from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class NotificationStatus(enum.Enum):
    gonderildi = "Gönderildi"
    hatali = "Hatalı"

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # İlişkiler
    recipient: Mapped["User"] = relationship(
        "User", back_populates="notifications"
    )