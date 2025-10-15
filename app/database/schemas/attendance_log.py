from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class AttendanceStatus(str, Enum):
    """Attendance status enum"""
    indi = "İndi"
    bindi = "Bindi"

class AttendanceLogBase(BaseModel):
    """Base schema for AttendanceLog"""
    student_id: str
    driver_id: str
    bus_id: str
    status: AttendanceStatus
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    log_time: datetime

class AttendanceLogCreate(AttendanceLogBase):
    """Schema for creating a new AttendanceLog"""
    pass

class AttendanceLogUpdate(BaseModel):
    """Schema for updating an AttendanceLog"""
    status: Optional[AttendanceStatus] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    log_time: Optional[datetime] = None

class AttendanceLog(AttendanceLogBase):
    """Schema for AttendanceLog responses"""
    id: str

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "student_id": "student123",
                "driver_id": "driver123",
                "bus_id": "bus123",
                "status": "Bindi",
                "latitude": 39.925533,
                "longitude": 32.866287,
                "log_time": "2025-10-14T10:00:00"
            }
        }