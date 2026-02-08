from typing import Optional
from pydantic import BaseModel

class StudentBusAssignmentBase(BaseModel):
    """Base schema for StudentBusAssignment"""
    bus_id: str
    student_id: str

class StudentBusAssignmentCreate(StudentBusAssignmentBase):
    """Schema for creating a new StudentBusAssignment"""
    pass

class StudentBusAssignmentUpdate(BaseModel):
    """Schema for updating a StudentBusAssignment"""
    bus_id: Optional[str] = None
    student_id: Optional[str] = None

class StudentBusAssignment(StudentBusAssignmentBase):
    """Schema for StudentBusAssignment responses"""
    id: str
    student: Optional["StudentBase"] = None
    bus: Optional["BusBase"] = None

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "bus_id": "bus123",
                "student_id": "student123",
                "student": {
                    "first_name": "Ali",
                    "last_name": "Veli",
                    "student_number": "1234"
                },
                "bus": {
                    "plate_number": "06 ABC 123"
                }
            }
        }

from .student import StudentBase
from .bus import BusBase