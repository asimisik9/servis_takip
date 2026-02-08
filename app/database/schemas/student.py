from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class StudentBase(BaseModel):
    """Base schema for Student"""
    full_name: str = Field(..., min_length=1, max_length=200)
    student_number: str = Field(..., min_length=1, max_length=50)
    school_id: str
    address: Optional[str] = Field(None, max_length=500)

class StudentCreate(StudentBase):
    """Schema for creating a new Student"""
    pass

class StudentUpdate(BaseModel):
    """Schema for updating a Student"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=200)
    student_number: Optional[str] = Field(None, min_length=1, max_length=50)
    school_id: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)

class StudentAddressUpdate(BaseModel):
    """Schema for updating only Student address"""
    address: str = Field(..., min_length=1, max_length=500)

class Student(StudentBase):
    """Schema for Student responses"""
    id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime
    school_name: Optional[str] = None

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "full_name": "Ali Yılmaz",
                "student_number": "2025001",
                "school_id": "school123",
                "created_at": "2025-10-14T10:00:00"
            }
        }