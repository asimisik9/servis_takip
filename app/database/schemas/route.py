# app/schemas/route.py
"""
Schemas for route optimization endpoints
"""

from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class RouteStop(BaseModel):
    """A single stop in the route (student pickup/dropoff)"""
    student_id: str
    full_name: str
    student_number: str
    address: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    sequence_order: int = Field(..., ge=1, description="Order in the optimized route")
    
    class Config:
        from_attributes = True


class OptimizedRouteResponse(BaseModel):
    """Response containing optimized bus route"""
    bus_id: str
    stops: List[RouteStop] = Field(default_factory=list)
    total_distance_meters: int = Field(
        ..., 
        ge=0, 
        description="Total distance in meters"
    )
    total_duration_seconds: int = Field(
        ..., 
        ge=0, 
        description="Total estimated driving time in seconds"
    )
    generated_at: datetime = Field(
        ..., 
        description="When the route was generated/optimized"
    )
    
    class Config:
        from_attributes = True


class RouteResponse(BaseModel):
    """Simple route response"""
    bus_id: str
    stops: List[RouteStop]
    
    class Config:
        from_attributes = True
