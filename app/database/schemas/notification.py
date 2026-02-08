from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class NotificationStatus(str, Enum):
    """Notification status enum"""
    gonderildi = "Gönderildi"
    hatali = "Hatalı"
    beklemede = "Beklemede"


class NotificationType(str, Enum):
    """Notification type enum"""
    eve_varis_eta = "eve_varis_eta"
    evden_alim_eta = "evden_alim_eta"
    okula_varis = "okula_varis"
    eve_birakildi = "eve_birakildi"
    genel = "genel"


class NotificationBase(BaseModel):
    """Base schema for Notification"""
    recipient_id: str
    title: str = "Servis Now"
    message: str
    notification_type: NotificationType = NotificationType.genel
    student_id: Optional[str] = None


class NotificationCreate(NotificationBase):
    """Schema for creating a new Notification"""
    pass


class NotificationUpdate(BaseModel):
    """Schema for updating a Notification"""
    message: Optional[str] = None
    status: Optional[NotificationStatus] = None
    is_read: Optional[bool] = None


class Notification(NotificationBase):
    """Schema for Notification responses"""
    id: str
    status: NotificationStatus
    is_read: bool = False
    created_at: datetime

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "recipient_id": "user123",
                "title": "Servis Bildirimi",
                "message": "Çocuğunuz servise bindi.",
                "notification_type": "okula_varis",
                "status": "Gönderildi",
                "is_read": False,
                "created_at": "2025-10-14T10:00:00"
            }
        }


class FCMTokenRegister(BaseModel):
    """Schema for registering FCM token"""
    fcm_token: str = Field(..., min_length=10, max_length=500)


class SendNotificationRequest(BaseModel):
    """Schema for sending notification via admin"""
    recipient_ids: List[str] = Field(..., min_length=1, max_length=100)
    title: str = Field(default="Servis Now", min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=1000)
    notification_type: NotificationType = NotificationType.genel
    student_id: Optional[str] = None


class NotificationResponse(BaseModel):
    """Standard notification response"""
    success: bool
    message: str
    notification_id: Optional[str] = None