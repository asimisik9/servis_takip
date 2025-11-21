from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AuditLogBase(BaseModel):
    action: str
    endpoint: str
    details: Optional[str] = None
    status_code: int

class AuditLogCreate(AuditLogBase):
    user_id: Optional[str] = None

class AuditLog(AuditLogBase):
    id: str
    user_id: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True
