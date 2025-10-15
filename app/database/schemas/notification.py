from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum

class NotificationStatus(str, Enum):
    """Notification status enum"""
    gonderildi = "Gönderildi"
    hatali = "Hatalı"

class NotificationBase(BaseModel):
    """Base schema for Notification"""
    recipient_id: str
    message: str
    status: NotificationStatus

class NotificationCreate(NotificationBase):
    """Schema for creating a new Notification"""
    pass

class NotificationUpdate(BaseModel):
    """Schema for updating a Notification"""
    message: Optional[str] = None
    status: Optional[NotificationStatus] = None

class Notification(NotificationBase):
    """Schema for Notification responses"""
    id: str
    created_at: datetime

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "recipient_id": "user123",
                "message": "Çocuğunuz servise bindi.",
                "status": "Gönderildi",
                "created_at": "2025-10-14T10:00:00"
            }
        }