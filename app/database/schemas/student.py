from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class StudentBase(BaseModel):
    """Base schema for Student"""
    full_name: str
    student_number: str
    school_id: str

class StudentCreate(StudentBase):
    """Schema for creating a new Student"""
    pass

class StudentUpdate(BaseModel):
    """Schema for updating a Student"""
    full_name: Optional[str] = None
    student_number: Optional[str] = None
    school_id: Optional[str] = None

class Student(StudentBase):
    """Schema for Student responses"""
    id: str
    created_at: datetime

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