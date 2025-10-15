from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from enum import Enum

class UserRole(str, Enum):
    veli = "Parent"
    sofor = "Driver"
    admin = "Admin"

class UserBase(BaseModel):
    """Base schema for User"""
    full_name: str
    email: EmailStr
    phone_number: str
    role: UserRole = UserRole.veli

class UserCreate(UserBase):
    """Schema for creating a new User"""
    password: str

class UserUpdate(BaseModel):
    """Schema for updating a User"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None

class User(UserBase):
    """Schema for User responses"""
    id: str
    created_at: datetime

    class Config:
        """Pydantic configuration"""
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1",
                "full_name": "Ahmet Yılmaz",
                "email": "ahmet@example.com",
                "phone_number": "+905551234567",
                "role": "Parent",
                "created_at": "2025-10-14T10:00:00"
            }
        }