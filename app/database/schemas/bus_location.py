from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class BusLocationBase(BaseModel):
    """Base schema for BusLocation"""
    bus_id: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    speed: float = Field(..., ge=0)

class BusLocationCreate(BusLocationBase):
    """Schema for creating a new BusLocation"""
    pass

class BusLocationUpdate(BaseModel):
    """Schema for updating a BusLocation"""
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    speed: Optional[float] = Field(None, ge=0)

class BusLocation(BusLocationBase):
    """Schema for BusLocation responses"""
    id: str
    timestamp: datetime

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "bus_id": "bus123",
                "latitude": 39.925533,
                "longitude": 32.866287,
                "speed": 45.5,
                "timestamp": "2025-10-14T10:00:00"
            }
        }