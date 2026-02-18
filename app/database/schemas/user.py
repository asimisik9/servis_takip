from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator
from enum import Enum
import re

class UserRole(str, Enum):
    veli = "veli"
    sofor = "sofor"
    admin = "admin"
    super_admin = "super_admin"

class UserBase(BaseModel):
    """Base schema for User"""
    full_name: str
    email: EmailStr
    phone_number: str
    role: UserRole = UserRole.veli

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Simple validation: must contain at least 10 digits
        digits = re.sub(r'\D', '', v)
        if len(digits) < 10:
            raise ValueError('Phone number must contain at least 10 digits')
        return v

class UserCreate(UserBase):
    """Schema for creating a new User"""
    password: str
    organization_id: Optional[str] = None # Allow specifying org (e.g. for super admin creating tenant admin)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[a-z]", v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserUpdate(BaseModel):
    """Schema for updating a User"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None
    organization_id: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r"[A-Z]", v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r"[a-z]", v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r"\d", v):
            raise ValueError('Password must contain at least one digit')
        return v

class User(UserBase):
    """Schema for User responses"""
    id: str
    is_active: bool = True
    is_email_verified: bool = False
    email_verified_at: Optional[datetime] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    organization: Optional["Organization"] = None
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
                "created_at": "2025-10-14T10:00:00",
                "organization": {
                    "name": "Atatürk İlkokulu",
                    "type": "school"
                }
            }
        }

from .organization import Organization
