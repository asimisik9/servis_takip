from typing import Optional
from pydantic import BaseModel

class ParentStudentRelationBase(BaseModel):
    """Base schema for ParentStudentRelation"""
    parent_id: str
    student_id: str

class ParentStudentRelationCreate(ParentStudentRelationBase):
    """Schema for creating a new ParentStudentRelation"""
    pass

class ParentStudentRelationUpdate(BaseModel):
    """Schema for updating a ParentStudentRelation"""
    parent_id: Optional[str] = None
    student_id: Optional[str] = None

class ParentStudentRelation(ParentStudentRelationBase):
    """Schema for ParentStudentRelation responses"""
    id: str

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "parent_id": "parent123",
                "student_id": "student123"
            }
        }