from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional
import googlemaps
import logging

from ..core.config import settings
from ..database.models.student import Student as StudentModel
from ..database.models.school import School as SchoolModel
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.schemas.student import StudentCreate, StudentUpdate
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)

class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _geocode_address(self, address: str):
        if not settings.GOOGLE_MAPS_API_KEY:
            return None, None
        
        gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        try:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                return location['lat'], location['lng']
        except Exception as e:
            print(f"Geocoding error: {e}")
        return None, None

    async def get_students(self, skip: int = 0, limit: int = 100) -> List[StudentModel]:
        query = select(StudentModel).options(selectinload(StudentModel.school)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_student_by_id(self, student_id: str) -> Optional[StudentModel]:
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_student(self, student: StudentCreate) -> StudentModel:
        query = select(StudentModel).where(StudentModel.student_number == student.student_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Student number already exists")

        lat, lng = None, None
        if student.address:
            lat, lng = self._geocode_address(student.address)

        new_student = StudentModel(
            id=str(uuid4()),
            full_name=student.full_name,
            student_number=student.student_number,
            school_id=student.school_id,
            address=student.address,
            latitude=lat,
            longitude=lng
        )
        self.db.add(new_student)
        await self.db.commit()
        await self.db.refresh(new_student)
        return await self.get_student_by_id(new_student.id)

    async def update_student(self, student_id: str, student_update: StudentUpdate) -> StudentModel:
        db_student = await self.get_student_by_id(student_id)
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")

        if student_update.student_number and student_update.student_number != db_student.student_number:
            query = select(StudentModel).where(StudentModel.student_number == student_update.student_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Student number already exists")

        if student_update.school_id:
            query = select(SchoolModel).where(SchoolModel.id == student_update.school_id)
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School not found")

        address_changed = False
        if student_update.address is not None:
            db_student.address = student_update.address
            lat, lng = self._geocode_address(student_update.address)
            db_student.latitude = lat
            db_student.longitude = lng
            address_changed = True

        if student_update.full_name is not None:
            db_student.full_name = student_update.full_name
        if student_update.student_number is not None:
            db_student.student_number = student_update.student_number
        if student_update.school_id is not None:
            db_student.school_id = student_update.school_id

        await self.db.commit()
        await self.db.refresh(db_student)
        
        # Invalidate route cache if address changed
        if address_changed:
            await self._invalidate_route_caches_for_student(student_id)
        
        return await self.get_student_by_id(db_student.id)

    async def delete_student(self, student_id: str):
        db_student = await self.get_student_by_id(student_id)
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        await self.db.delete(db_student)
        await self.db.commit()
    
    async def _invalidate_route_caches_for_student(self, student_id: str) -> None:
        """Invalidate route caches for all buses that have this student assigned"""
        try:
            # Get all bus assignments for this student
            query = select(StudentBusAssignment).where(
                StudentBusAssignment.student_id == student_id
            )
            result = await self.db.execute(query)
            assignments = result.scalars().all()
            
            # Invalidate cache for each bus
            for assignment in assignments:
                cache_key = f"route:{assignment.bus_id}"
                await redis_manager.delete(cache_key)
                logger.info(f"Route cache invalidated for bus {assignment.bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate route caches for student {student_id}: {str(e)}")
