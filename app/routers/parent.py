from fastapi import APIRouter, Depends, Query
from typing import List, Annotated
from datetime import date
from app.database.schemas.user import User
from app.database.schemas.student import Student, StudentAddressUpdate
from app.database.schemas.bus_location import BusLocation
from app.database.schemas.attendance_log import AttendanceLog
from app.database.schemas.dashboard import DashboardResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_db, get_current_parent_user
from ..services.parent_service import ParentService

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
    service = ParentService(db)
    return await service.get_parent_students(current_user.id)

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
async def report_student_absence(
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
