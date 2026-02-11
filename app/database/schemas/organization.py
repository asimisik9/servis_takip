# app/database/schemas/organization.py
from pydantic import BaseModel, Field, EmailStr, field_validator
from typing import Optional
from datetime import datetime, date
from enum import Enum
import re


class OrganizationType(str, Enum):
    school = "school"
    transport_company = "transport_company"


# Organization Schemas
class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    type: OrganizationType


class OrganizationAdminCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone_number: str
    password: str = Field(..., min_length=8, max_length=255)

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class OrganizationCreate(OrganizationBase):
    admin: Optional[OrganizationAdminCreate] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    is_active: Optional[bool] = None


class Organization(OrganizationBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrganizationWithStats(Organization):
    """Organization with additional statistics"""
    user_count: int = 0
    school_count: int = 0  # For school type
    bus_count: int = 0  # For transport_company type
    contract_count: int = 0


# Contract Schemas
class SchoolCompanyContractBase(BaseModel):
    school_org_id: str
    company_org_id: str
    start_date: date


class SchoolCompanyContractCreate(SchoolCompanyContractBase):
    end_date: Optional[date] = None


class SchoolCompanyContractUpdate(BaseModel):
    end_date: Optional[date] = None
    is_active: Optional[bool] = None


class SchoolCompanyContract(SchoolCompanyContractBase):
    id: str
    end_date: Optional[date] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SchoolCompanyContractWithOrgs(SchoolCompanyContract):
    """Contract with organization details"""
    school_org_name: str
    company_org_name: str
