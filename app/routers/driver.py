from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Annotated
from datetime import date
from ..database.schemas.user import User
from ..database.schemas.student import Student
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLog
from ..database.schemas.bus_location import BusLocationCreate, BusLocation
from .auth import get_current_driver_user
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import models
from ..database.database import AsyncSessionLocal


# DB session dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

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
    Opsiyonel olarak tarih parametresi alır.
    """
    # Şoförün şu anki otobüsünü bul
    query = select(models.Bus).where(models.Bus.current_driver_id == current_user.id)
    result = await db.execute(query)
    bus = result.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Driver has no assigned bus")
    # Otobüse atanan öğrencileri bul
    query = select(models.Student).join(models.StudentBusAssignment).where(models.StudentBusAssignment.bus_id == bus.id)
    result = await db.execute(query)
    students = result.scalars().all()
    return students

@router.post("/attendance/log", response_model=AttendanceLog)
async def create_attendance_log(
    attendance: AttendanceLogCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Öğrencinin servise bindiğini veya indiğini kaydeder.
    """
    from uuid import uuid4
    from datetime import datetime
    # Öğrenci ve otobüs gerçekten bu şoföre mi ait kontrolü
    query = select(models.Bus).where(models.Bus.current_driver_id == current_user.id)
    result = await db.execute(query)
    bus = result.scalar_one_or_none()
    if not bus or bus.id != attendance.bus_id:
        raise HTTPException(status_code=400, detail="Bus not assigned to this driver")
    # Öğrenci bu otobüse atanmış mı kontrolü
    query = select(models.StudentBusAssignment).where(
        models.StudentBusAssignment.bus_id == bus.id,
        models.StudentBusAssignment.student_id == attendance.student_id
    )
    result = await db.execute(query)
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=400, detail="Student not assigned to this bus")
    # Yoklama kaydını oluştur
    new_log = models.AttendanceLog(
        id=str(uuid4()),
        student_id=attendance.student_id,
        bus_id=attendance.bus_id,
        attended=attendance.attended,
        direction=attendance.direction,
        timestamp=datetime.now()
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    return new_log

@router.post("/buses/me/location", response_model=BusLocation)
async def update_bus_location(
    location: BusLocationCreate,
    current_user: Annotated[User, Depends(get_current_driver_user)],
    db: AsyncSession = Depends(get_db)
):
    """
    Servisin anlık konumunu kaydeder.
    """
    from uuid import uuid4
    from datetime import datetime
    # Şoförün otobüsünü bul
    query = select(models.Bus).where(models.Bus.current_driver_id == current_user.id)
    result = await db.execute(query)
    bus = result.scalar_one_or_none()
    if not bus:
        raise HTTPException(status_code=404, detail="Driver has no assigned bus")
    # Konum kaydını oluştur
    new_location = models.BusLocation(
        id=str(uuid4()),
        bus_id=bus.id,
        latitude=location.latitude,
        longitude=location.longitude,
        timestamp=datetime.now()
    )
    db.add(new_location)
    await db.commit()
    await db.refresh(new_location)
    return new_location