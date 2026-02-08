from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Optional

from ..database import models
from ..database.schemas.attendance_log import AttendanceLogCreate, AttendanceLogRequest
from ..database.schemas.bus_location import BusLocationCreate
from ..core.exceptions import ResourceNotFoundException, BusinessRuleException

class DriverService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_driver_bus(self, driver_id: str) -> Optional[models.Bus]:
        query = select(models.Bus).where(models.Bus.current_driver_id == driver_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_driver_bus_id(self, driver_id: str) -> Optional[str]:
        """Get the bus ID assigned to a driver"""
        bus = await self.get_driver_bus(driver_id)
        return bus.id if bus else None

    async def get_roster(self, driver_id: str) -> List[models.Student]:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")
        
        # school ilişkisini eager load yapıyoruz
        query = (
            select(models.Student)
            .join(models.StudentBusAssignment)
            .where(models.StudentBusAssignment.bus_id == bus.id)
            .options(selectinload(models.Student.school))
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_attendance_log(self, driver_id: str, attendance: AttendanceLogRequest) -> models.AttendanceLog:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")
        
        # Check if student is assigned to this bus
        query = select(models.StudentBusAssignment).where(
            models.StudentBusAssignment.bus_id == bus.id,
            models.StudentBusAssignment.student_id == attendance.student_id
        )
        result = await self.db.execute(query)
        if not result.scalar_one_or_none():
            raise BusinessRuleException("Student not assigned to this bus")
            
        new_log = models.AttendanceLog(
            id=str(uuid4()),
            student_id=attendance.student_id,
            bus_id=bus.id, # Otobüs ID'sini şoförden alıyoruz
            driver_id=driver_id, # Driver ID'sini tokendan alıyoruz
            status=attendance.status,
            latitude=attendance.latitude,
            longitude=attendance.longitude,
            log_time=attendance.log_time
        )
        self.db.add(new_log)
        await self.db.commit()
        await self.db.refresh(new_log)
        return new_log

    async def update_location(self, driver_id: str, location: BusLocationCreate) -> models.BusLocation:
        bus = await self.get_driver_bus(driver_id)
        if not bus:
            raise ResourceNotFoundException("Driver has no assigned bus")
            
        new_location = models.BusLocation(
            id=str(uuid4()),
            bus_id=bus.id,
            latitude=location.latitude,
            longitude=location.longitude,
            speed=location.speed,
            timestamp=datetime.now(timezone.utc)
        )
        self.db.add(new_location)
        await self.db.commit()
        await self.db.refresh(new_location)
        return new_location
