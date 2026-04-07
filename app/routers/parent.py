import json
from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from typing import List, Annotated
from datetime import date
from ..database.schemas.user import User
from ..database.schemas.student import Student, StudentAddressUpdate
from ..database.schemas.bus_location import BusLocation
from ..database.schemas.attendance_log import AttendanceLog
from ..database.schemas.absence import AbsenceStatusResponse
from ..database.schemas.dashboard import DashboardResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_parent_user
from ..services.parent_service import ParentService
from ..core.limiter import limiter
from ..core.redis import redis_manager

router = APIRouter(
    prefix="/parent",
    tags=["parent"]
)

@router.put("/students/{student_id}/address", response_model=Student)
async def update_student_address(
    student_id: str,
    address_update: StudentAddressUpdate,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin adresini günceller.
    Adres güncellendiğinde enlem ve boylam otomatik olarak yeniden hesaplanır.
    """
    service = ParentService(db)
    return await service.update_student_address(current_user.id, student_id, address_update)

@router.get("/me/students", response_model=List[Student])
async def get_parent_students(
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Velinin öğrencilerini listeler.
    """
    cache_key = f"parent_students:{current_user.id}"
    cached = await redis_manager.get(cache_key)
    if cached:
        return json.loads(cached)

    service = ParentService(db)
    students = await service.get_parent_students(current_user.id)
    await redis_manager.set(cache_key, json.dumps(jsonable_encoder(students)), ex=300)
    return students

@router.get("/students/{student_id}/bus/location", response_model=BusLocation)
async def get_student_bus_location(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin servisinin anlık konumunu getirir.
    """
    service = ParentService(db)
    return await service.get_student_bus_location(current_user.id, student_id)

@router.get("/students/{student_id}/attendance/history", response_model=List[AttendanceLog])
async def get_student_attendance_history(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db),
    date: date | None = Query(default=None, description="Belirli bir tarihteki yoklama kayıtlarını filtrelemek için kullanılır")
):
    """
    Öğrencinin geçmiş yoklama kayıtlarını listeler.
    Opsiyonel olarak tarih parametresi alır.
    """
    service = ParentService(db)
    return await service.get_student_attendance_history(current_user.id, student_id, date)

@router.get("/students/{student_id}/dashboard", response_model=DashboardResponse)
async def get_student_dashboard(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin dashboard verilerini (ETA, Şoför, Durum) getirir.
    """
    service = ParentService(db)
    return await service.get_student_dashboard_data(current_user.id, student_id)

@router.post("/students/{student_id}/absent")
@limiter.limit("10/minute")
async def report_student_absence(
    request: Request,
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin o gün gelmeyeceğini bildirir.
    """
    service = ParentService(db)
    await service.report_absence(current_user.id, student_id)
    return {"message": "Absence reported successfully"}


@router.get("/students/{student_id}/absence/status", response_model=AbsenceStatusResponse)
async def get_student_absence_status(
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin bugün için devamsızlık durumunu getirir.
    """
    service = ParentService(db)
    return await service.get_absence_status(current_user.id, student_id)


@router.delete("/students/{student_id}/absent")
@limiter.limit("10/minute")
async def cancel_student_absence(
    request: Request,
    student_id: str,
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin o gün için bildirilen devamsızlığını geri alır.
    """
    service = ParentService(db)
    await service.cancel_absence(current_user.id, student_id)
    return {"message": "Absence cancelled successfully"}
