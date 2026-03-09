from fastapi import APIRouter, Depends, status, HTTPException, Query
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.bus import Bus, BusCreate, BusUpdate
from ...database.schemas.route import OptimizedRouteResponse
from ...database.schemas.common import PaginatedResponse
from ...dependencies import get_db, get_current_admin_user
from ...services.bus_service import BusService
from ...services.route_service import RouteService

router = APIRouter(tags=["admin-buses"])

@router.get("/buses", response_model=PaginatedResponse[Bus])
async def list_buses(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    school_id: Annotated[str | None, Query()] = None,
    organization_id: Annotated[str | None, Query()] = None,
):
    """List buses with tenant filtering and pagination."""
    service = BusService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    org_filter = organization_id if current_user.role.value == "super_admin" else None
    buses, total = await service.get_buses(
        skip=skip, 
        limit=limit, 
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type,
        school_id=school_id,
        organization_filter=org_filter,
    )
    return PaginatedResponse(items=buses, total=total, skip=skip, limit=limit)

@router.post("/buses", response_model=Bus, status_code=status.HTTP_201_CREATED)
async def create_bus(
    bus: BusCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    return await service.create_bus(
        bus,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )

@router.put("/buses/{bus_id}", response_model=Bus)
async def update_bus(
    bus_id: str,
    bus: BusUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    return await service.update_bus(
        unquote(bus_id), 
        bus,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )

@router.get("/buses/{bus_id}", response_model=Bus)
async def get_bus(
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    bus = await service.get_bus_by_id(
        unquote(bus_id),
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return bus

@router.delete("/buses/{bus_id}", status_code=status.HTTP_200_OK)
async def delete_bus(
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    org_type = current_user.organization.type.value if current_user.organization else None
    await service.delete_bus(
        unquote(bus_id),
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    return {"detail": "Bus deleted successfully"}

@router.get("/buses/{bus_id}/route", response_model=OptimizedRouteResponse)
async def get_bus_route(
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Belirli bir servis için optimize edilmiş rotayı getirir.
    Rota, atanan öğrencilerin adreslerine göre en kısa/en uygun sırada hesaplanır.
    
    - Google Maps API ile optimize edilir
    - Sonuçlar 30 dakika boyunca cache'lenir
    - Öğrencilerin enlem/boylam bilgisi gereklidir
    
    Args:
        bus_id: Servisin UUID'si
    """
    bus_id = unquote(bus_id)
    bus_service = BusService(db)
    route_service = RouteService(db)
    org_type = current_user.organization.type.value if current_user.organization else None

    bus = await bus_service.get_bus_by_id(
        bus_id,
        current_user_org_id=current_user.organization_id,
        current_user_org_type=org_type
    )
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    
    try:
        return await route_service.get_optimized_route(bus_id, current_user_org_id=str(current_user.organization_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to calculate route. Please try again later."
        )
