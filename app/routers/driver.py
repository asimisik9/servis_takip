from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from typing import List, Annotated
from ..database.schemas.user import User
from ..database.schemas.student import Student
from ..database.schemas.attendance_log import AttendanceLog, AttendanceLogRequest
from ..database.schemas.bus_location import BusLocationCreate, BusLocation
from ..database.schemas.route import OptimizedRouteResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_driver_user
from ..services.driver_service import DriverService
from ..services.route_service import RouteService
from ..services.route_progress_service import RouteProgressService
from ..core.limiter import limiter

router = APIRouter(
    prefix="/driver",
    tags=["driver"]
)

@router.get("/me/roster", response_model=List[Student])
async def get_driver_roster(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Şoförün sorumlu olduğu servisteki öğrenci listesini getirir.
    """
    service = DriverService(db)
    return await service.get_roster(current_user.id)

@router.post("/attendance/log", response_model=AttendanceLog)
@limiter.limit("120/minute")
async def create_attendance_log(
    request: Request,
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
@limiter.limit("30/minute")
async def update_bus_location(
    request: Request,
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
    db: AsyncSession = Depends(get_db),
    origin_lat: float | None = Query(default=None, ge=-90, le=90),
    origin_lng: float | None = Query(default=None, ge=-180, le=180),
    exclude_student_ids: str | None = Query(default=None, description="Comma-separated student IDs to exclude (visited)"),
    include_all: bool = Query(default=False, description="If true, includes all students regardless of visited list"),
    trip_type: str = Query(default="to_school", description="Trip type: 'to_school' (pickup) or 'from_school' (dropoff)")
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
    progress_service = RouteProgressService()
    
    # Get driver's assigned bus
    bus_id = await driver_service.get_driver_bus_id(current_user.id)
    if not bus_id:
        raise HTTPException(
            status_code=404,
            detail="Driver has no assigned bus"
        )
    
    # Build origin tuple if provided
    origin = None
    if origin_lat is not None and origin_lng is not None:
        origin = (origin_lat, origin_lng)

    # Parse exclude list if provided
    exclude_list = None
    if exclude_student_ids:
        exclude_list = [s.strip() for s in exclude_student_ids.split(",") if s.strip()]

    # Validate trip_type
    if trip_type not in ("to_school", "from_school"):
        raise HTTPException(
            status_code=400,
            detail="trip_type must be 'to_school' or 'from_school'"
        )

    # Save trip_type to Redis for parent app synchronization
    from ..core.redis import redis_manager
    await redis_manager.set(f"bus:{bus_id}:trip_type", trip_type, ex=3600)  # 1 hour TTL

    # Get optimized route for the bus
    try:
        return await route_service.get_optimized_route(
            bus_id=bus_id,
            origin=origin,
            exclude_student_ids=exclude_list,
            include_all=include_all,
            trip_type=trip_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate route. Please try again later."
        )


@router.get("/buses/me/route/visited", response_model=list[str])
async def get_visited_students(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    driver_service = DriverService(db)
    bus_id = await driver_service.get_driver_bus_id(current_user.id)
    if not bus_id:
        raise HTTPException(status_code=404, detail="Driver has no assigned bus")
    progress = RouteProgressService()
    return await progress.get_visited(bus_id)


@router.post("/buses/me/route/visited/{student_id}", status_code=status.HTTP_200_OK)
async def mark_student_visited(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    driver_service = DriverService(db)
    bus_id = await driver_service.get_driver_bus_id(current_user.id)
    if not bus_id:
        raise HTTPException(status_code=404, detail="Driver has no assigned bus")
    progress = RouteProgressService()
    await progress.add_visited(bus_id, student_id)
    return {"detail": "Visited marked"}


@router.delete("/buses/me/route/visited", status_code=status.HTTP_200_OK)
async def clear_visited_students(
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    driver_service = DriverService(db)
    bus_id = await driver_service.get_driver_bus_id(current_user.id)
    if not bus_id:
        raise HTTPException(status_code=404, detail="Driver has no assigned bus")
    progress = RouteProgressService()
    await progress.clear(bus_id)
    return {"detail": "Visited cleared"}
