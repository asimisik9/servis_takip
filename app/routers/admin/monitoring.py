from fastapi import APIRouter, Depends
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from ...database.schemas.user import User
from ...database.schemas.bus_location import BusLocation
from ...database.schemas.attendance_log import AttendanceLog
from ...dependencies import get_db, get_current_admin_user
from ...services.bus_service import BusService
from ...services.attendance_service import AttendanceService

router = APIRouter(tags=["admin-monitoring"])

@router.get("/buses/locations", response_model=List[BusLocation])
async def get_all_bus_locations(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    return await service.get_bus_locations()

@router.get("/logs/attendance", response_model=List[AttendanceLog])
async def get_attendance_logs(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    start_date: date = None,
    end_date: date = None,
    bus_id: str = None,
    student_id: str = None,
    skip: int = 0,
    limit: int = 100
):
    service = AttendanceService(db)
    return await service.get_attendance_logs(start_date, end_date, bus_id, student_id, skip, limit)
