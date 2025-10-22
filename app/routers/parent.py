from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Annotated
from datetime import date
from app.database.schemas.user import User
from app.database.schemas.student import Student
from app.database.schemas.bus_location import BusLocation
from app.database.schemas.attendance_log import AttendanceLog
from app.routers.auth import get_current_parent_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import models
from app.database.database import AsyncSessionLocal

router = APIRouter(
    prefix="/parent",
    tags=["parent"]
)

# DB session dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

@router.get("/me/students", response_model=List[Student])
async def get_parent_students(
    current_user: Annotated[User, Depends(get_current_parent_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Velinin öğrencilerini listeler.
    """
    # ParentStudentRelation ile ilişkilendirilmiş öğrencileri getir
    query = select(models.Student).join(models.ParentStudentRelation).where(models.ParentStudentRelation.parent_id == current_user.id)
    result = await db.execute(query)
    students = result.scalars().all()
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
    # Önce öğrenci gerçekten bu velinin mi kontrol et
    query = select(models.ParentStudentRelation).where(
        models.ParentStudentRelation.parent_id == current_user.id,
        models.ParentStudentRelation.student_id == student_id
    )
    result = await db.execute(query)
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(status_code=404, detail="Student not found or not your child")
    # Öğrencinin atandığı otobüsü bul
    query = select(models.StudentBusAssignment).where(models.StudentBusAssignment.student_id == student_id)
    result = await db.execute(query)
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Student has no assigned bus")
    # Otobüsün son konumunu bul
    query = select(models.BusLocation).where(models.BusLocation.bus_id == assignment.bus_id).order_by(models.BusLocation.timestamp.desc())
    result = await db.execute(query)
    bus_location = result.scalars().first()
    if not bus_location:
        raise HTTPException(status_code=404, detail="Bus location not found")
    return bus_location

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
    # Önce öğrenci gerçekten bu velinin mi kontrol et
    query = select(models.ParentStudentRelation).where(
        models.ParentStudentRelation.parent_id == current_user.id,
        models.ParentStudentRelation.student_id == student_id
    )
    result = await db.execute(query)
    relation = result.scalar_one_or_none()
    if not relation:
        raise HTTPException(status_code=404, detail="Student not found or not your child")
    # Yoklama kayıtlarını getir
    query = select(models.AttendanceLog).where(models.AttendanceLog.student_id == student_id)
    if date:
        from datetime import datetime, timedelta
        start = datetime.combine(date, datetime.min.time())
        end = datetime.combine(date, datetime.max.time())
        query = query.where(models.AttendanceLog.timestamp >= start, models.AttendanceLog.timestamp <= end)
    query = query.order_by(models.AttendanceLog.timestamp.desc())
    result = await db.execute(query)
    logs = result.scalars().all()
    return logs