from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from datetime import date
from ..database.schemas.user import User
from ..database.schemas.student import Student
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLog
from ..database.schemas.bus_location import BusLocationCreate, BusLocation
from .auth import get_current_driver_user

router = APIRouter(
    prefix="/driver",
    tags=["driver"]
)

@router.get("/me/roster", response_model=List[Student])
async def get_driver_roster(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    date: date = None
):
    """
    Şoförün sorumlu olduğu servisteki öğrenci listesini getirir.
    Opsiyonel olarak tarih parametresi alır.
    """
    # TODO: Implement roster retrieval logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented"
    )

@router.post("/attendance/log", response_model=AttendanceLog)
async def create_attendance_log(
    attendance: AttendanceLogCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)]
):
    """
    Öğrencinin servise bindiğini veya indiğini kaydeder.
    """
    # TODO: Implement attendance logging logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented"
    )

@router.post("/buses/me/location", response_model=BusLocation)
async def update_bus_location(
    location: BusLocationCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)]
):
    """
    Servisin anlık konumunu kaydeder.
    """
    # TODO: Implement location update logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented"
    )