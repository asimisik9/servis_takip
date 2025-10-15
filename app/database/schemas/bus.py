from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class BusBase(BaseModel):
    """Base schema for Bus"""
    plate_number: str
    capacity: int = Field(gt=0)  # positive integer validation
    school_id: str
    current_driver_id: str

class BusCreate(BusBase):
    """Schema for creating a new Bus"""
    pass

class BusUpdate(BaseModel):
    """Schema for updating a Bus"""
    plate_number: Optional[str] = None
    capacity: Optional[int] = Field(None, gt=0)  # positive integer validation
    school_id: Optional[str] = None
    current_driver_id: Optional[str] = None

class Bus(BusBase):
    """Schema for Bus responses"""
    id: str

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "plate_number": "06 ABC 123",
                "capacity": 30,
                "school_id": "school123",
                "current_driver_id": "driver123"
            }
        }