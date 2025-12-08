from fastapi import APIRouter, Depends, status, HTTPException
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.bus import Bus, BusCreate, BusUpdate
from ...database.schemas.route import OptimizedRouteResponse
from ...dependencies import get_db, get_current_admin_user
from ...services.bus_service import BusService
from ...services.route_service import RouteService

router = APIRouter(tags=["admin-buses"])

@router.get("/buses", response_model=List[Bus])
async def list_buses(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    service = BusService(db)
    return await service.get_buses(skip, limit)

@router.post("/buses", response_model=Bus, status_code=status.HTTP_201_CREATED)
async def create_bus(
    bus: BusCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    return await service.create_bus(bus)

@router.put("/buses/{bus_id}", response_model=Bus)
async def update_bus(
    bus_id: str,
    bus: BusUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    return await service.update_bus(unquote(bus_id), bus)

@router.delete("/buses/{bus_id}", status_code=status.HTTP_200_OK)
async def delete_bus(
    bus_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = BusService(db)
    await service.delete_bus(unquote(bus_id))
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
    route_service = RouteService(db)
    bus_id = unquote(bus_id)
    
    try:
        return await route_service.get_optimized_route(bus_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate route: {str(e)}"
        )
