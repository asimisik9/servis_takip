from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from datetime import date
from ..database.schemas.user import User
from ..database.schemas.student import Student
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLog, AttendanceLogRequest
from ..database.schemas.bus_location import BusLocationCreate, BusLocation
from ..database.schemas.route import OptimizedRouteResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_driver_user
from ..services.driver_service import DriverService
from ..services.route_service import RouteService

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
    attendance: AttendanceLogRequest,
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

@router.get("/buses/me/route", response_model=OptimizedRouteResponse)
async def get_driver_bus_route(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Şoförün sorumlu olduğu servis için optimize edilmiş rotayı getirir.
    Rota, atanan öğrencilerin adreslerine göre en kısa/en uygun sırada hesaplanır.
    
    - Google Maps API ile optimize edilir
    - Sonuçlar 30 dakika boyunca cache'lenir
    - Öğrencilerin enlem/boylam bilgisi gereklidir
    """
    driver_service = DriverService(db)
    route_service = RouteService(db)
    
    # Get driver's assigned bus
    bus_id = await driver_service.get_driver_bus_id(current_user.id)
    if not bus_id:
        raise HTTPException(
            status_code=404,
            detail="Driver has no assigned bus"
        )
    
    # Get optimized route for the bus
    try:
        return await route_service.get_optimized_route(bus_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate route: {str(e)}"
        )
