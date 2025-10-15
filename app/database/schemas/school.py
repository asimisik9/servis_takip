from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class SchoolBase(BaseModel):
    """Base schema for School"""
    school_name: str
    school_address: str
    contact_person_id: str

class SchoolCreate(SchoolBase):
    """Schema for creating a new School"""
    pass

class SchoolUpdate(BaseModel):
    """Schema for updating a School"""
    school_name: Optional[str] = None
    school_address: Optional[str] = None
    contact_person_id: Optional[str] = None

class School(SchoolBase):
    """Schema for School responses"""
    id: str

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "school_name": "Atatürk İlkokulu",
                "school_address": "Ankara, Çankaya",
                "contact_person_id": "user123"
            }
        }