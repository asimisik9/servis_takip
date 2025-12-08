from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from typing import List, Optional
from datetime import date, datetime

from ..database.models.student import Student as StudentModel
from ..database.models.parent_student_relation import ParentStudentRelation
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.bus_location import BusLocation
from ..database.models.attendance_log import AttendanceLog
from sqlalchemy.orm import joinedload
from ..database.models.bus import Bus
from ..database.models.user import User
from ..database.schemas.dashboard import DashboardResponse
from ..database.schemas.student import StudentAddressUpdate
from .student_service import StudentService

class ParentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_student_address(self, parent_id: str, student_id: str, address_update: StudentAddressUpdate):
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Use StudentService to update address
        student_service = StudentService(self.db)
        
        # We need to construct a StudentUpdate object, but StudentService.update_student expects StudentUpdate
        # Let's import StudentUpdate inside the method to avoid circular imports if any, or just use what we have.
        from ..database.schemas.student import StudentUpdate
        
        update_data = StudentUpdate(address=address_update.address)
        return await student_service.update_student(student_id, update_data)

    async def get_parent_students(self, parent_id: str) -> List[StudentModel]:
        query = select(StudentModel).options(joinedload(StudentModel.school)).join(ParentStudentRelation).where(ParentStudentRelation.parent_id == parent_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_student_bus_location(self, parent_id: str, student_id: str) -> BusLocation:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Get assignment
        query = select(StudentBusAssignment).where(StudentBusAssignment.student_id == student_id)
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Student has no assigned bus")

        # Get location
        query = select(BusLocation).where(BusLocation.bus_id == assignment.bus_id).order_by(BusLocation.timestamp.desc())
        bus_location = (await self.db.execute(query)).scalars().first()
        
        if not bus_location:
            raise HTTPException(status_code=404, detail="Bus location not found")
            
        return bus_location

    async def get_student_attendance_history(self, parent_id: str, student_id: str, filter_date: Optional[date] = None) -> List[AttendanceLog]:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        query = select(AttendanceLog).where(AttendanceLog.student_id == student_id)
        
        if filter_date:
            start = datetime.combine(filter_date, datetime.min.time())
            end = datetime.combine(filter_date, datetime.max.time())
            query = query.where(AttendanceLog.timestamp >= start, AttendanceLog.timestamp <= end)
            
        query = query.order_by(AttendanceLog.timestamp.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_student_dashboard_data(self, parent_id: str, student_id: str) -> DashboardResponse:
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")

        # Get assignment with Bus and Driver
        query = select(StudentBusAssignment).options(
            joinedload(StudentBusAssignment.bus).joinedload(Bus.current_driver)
        ).where(StudentBusAssignment.student_id == student_id)
        
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        
        if not assignment or not assignment.bus:
             return DashboardResponse(
                 tripStatus="inactive",
                 minutesLeft=None,
                 driverName=None,
                 driverPhone=None,
                 plateNumber=None
             )

        bus = assignment.bus
        driver = bus.current_driver
        
        # Logic to determine status (Simplified for now)
        # In a real app, we would check active trips, time of day, etc.
        # For now, if there is a recent location update (last 30 mins), we assume active.
        
        query = select(BusLocation).where(BusLocation.bus_id == bus.id).order_by(BusLocation.timestamp.desc())
        location = (await self.db.execute(query)).scalars().first()
        
        trip_status = "inactive"
        minutes_left = None
        
        if location:
            # Check if location is recent (e.g. within 30 mins)
            # For demo purposes, let's assume it's active if we have a location
            # We can toggle between to_school and to_home based on time of day
            now = datetime.now()
            
            # TEST İÇİN GÜNCELLEME: Saat kontrolünü esnetiyoruz (Tüm gün aktif)
            if now.hour < 12:
                trip_status = "to_school"
            else:
                trip_status = "to_home"
            
            # Mock ETA calculation
            minutes_left = 15 

        return DashboardResponse(
            tripStatus=trip_status,
            minutesLeft=minutes_left,
            driverName=driver.full_name if driver else None,
            driverPhone=driver.phone_number if driver else None,
            plateNumber=bus.plate_number,
            busId=bus.id
        )

    async def report_absence(self, parent_id: str, student_id: str):
        # Check relation
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.parent_id == parent_id,
            ParentStudentRelation.student_id == student_id
        )
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found or not your child")
            
        # In a real application, we would save this to an Absence table
        # and notify the driver/admin.
        # For now, we just return success.
        return True
