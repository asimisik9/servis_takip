from pydantic import BaseModel, Field
from typing import Optional

class DashboardResponse(BaseModel):
    trip_status: str = Field(..., alias="tripStatus")
    minutes_left: Optional[int] = Field(None, alias="minutesLeft")
    driver_name: Optional[str] = Field(None, alias="driverName")
    driver_phone: Optional[str] = Field(None, alias="driverPhone")
    plate_number: Optional[str] = Field(None, alias="plateNumber")

    class Config:
        populate_by_name = True
        from_attributes = True
