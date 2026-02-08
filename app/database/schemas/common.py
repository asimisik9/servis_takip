# app/database/schemas/common.py
"""Common schemas for API responses"""
from pydantic import BaseModel
from typing import Generic, TypeVar, List, Optional

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    Returns total count for UI pagination support.
    """
    items: List[T]
    total: int
    skip: int
    limit: int
    
    @property
    def has_more(self) -> bool:
        return self.skip + len(self.items) < self.total
    
    @property
    def page(self) -> int:
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1
    
    @property
    def pages(self) -> int:
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 1


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str
    error_code: Optional[str] = None
