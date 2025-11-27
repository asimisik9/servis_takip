from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from datetime import date
from ..database.schemas.user import User
from ..database.schemas.student import Student
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLog
from ..database.schemas.bus_location import BusLocationCreate, BusLocation
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_driver_user
from ..services.driver_service import DriverService

router = APIRouter(
    prefix="/driver",
    tags=["driver"]
)

@router.get("/me/roster", response_model=List[Student])
async def get_driver_roster(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db),
    date: date = None
):
    """
    Şoförün sorumlu olduğu servisteki öğrenci listesini getirir.
    """
    service = DriverService(db)
    return await service.get_roster(current_user.id)

@router.post("/attendance/log", response_model=AttendanceLog)
async def create_attendance_log(
    attendance: AttendanceLogCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin servise bindiğini veya indiğini kaydeder.
    """
    service = DriverService(db)
    return await service.create_attendance_log(current_user.id, attendance)

@router.post("/buses/me/location", response_model=BusLocation)
async def update_bus_location(
    location: BusLocationCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Servisin anlık konumunu kaydeder.
    """
    service = DriverService(db)
    return await service.update_location(current_user.id, location)