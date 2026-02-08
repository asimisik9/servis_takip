from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional, Tuple
import httpx
import logging

from ..core.config import settings
from ..database.models.student import Student as StudentModel
from ..database.models.school import School as SchoolModel
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.attendance_log import AttendanceLog
from ..database.schemas.student import StudentCreate, StudentUpdate
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)

class StudentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _geocode_address(self, address: str) -> tuple[Optional[float], Optional[float]]:
        """Convert address to coordinates using Google Maps Geocoding API (async)"""
        if not settings.GOOGLE_MAPS_API_KEY:
            return None, None
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": settings.GOOGLE_MAPS_API_KEY}
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                result = response.json()
            
            if result.get("status") == "OK" and result.get("results"):
                location = result["results"][0]["geometry"]["location"]
                return location["lat"], location["lng"]
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
        return None, None

    async def get_students(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        school_id: Optional[str] = None
    ) -> Tuple[List[StudentModel], int]:
        """
        Get students with tenant filtering and total count.
        Filters by school's organization_id when current_user has org.
        Optionally filters by specific school_id.
        Returns: (students, total_count)
        """
        query = select(StudentModel).options(selectinload(StudentModel.school))
        count_query = select(func.count()).select_from(StudentModel)
        
        # Tenant filter - join with school to filter by org
        if current_user_org_id is not None:
            query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            count_query = count_query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            
        # Specific School Filter
        if school_id:
            query = query.where(StudentModel.school_id == school_id)
            # If we already joined SchoolModel above, we don't need to join again, but for safety in count query:
            if current_user_org_id is None: # If not joined yet
                 count_query = count_query.where(StudentModel.school_id == school_id)
            else:
                 count_query = count_query.where(StudentModel.school_id == school_id)
        
        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_student_by_id(self, student_id: str) -> Optional[StudentModel]:
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_student(self, student: StudentCreate, current_user_org_id: Optional[str] = None) -> StudentModel:
        query = select(StudentModel).where(StudentModel.student_number == student.student_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Student number already exists")

        # Validate school exists and verify tenant
        query = select(SchoolModel).where(SchoolModel.id == student.school_id)
        if current_user_org_id:
            query = query.where(SchoolModel.organization_id == current_user_org_id)
            
        school = (await self.db.execute(query)).scalar_one_or_none()
        if not school:
            raise HTTPException(status_code=400, detail="School not found or access denied")

        lat, lng = None, None
        if student.address:
            lat, lng = await self._geocode_address(student.address)

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

    async def update_student(self, student_id: str, student_update: StudentUpdate, current_user_org_id: Optional[str] = None) -> StudentModel:
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        if current_user_org_id:
            query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            
        db_student = (await self.db.execute(query)).scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")

        if student_update.student_number and student_update.student_number != db_student.student_number:
            query = select(StudentModel).where(StudentModel.student_number == student_update.student_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Student number already exists")

        if student_update.school_id:
            query = select(SchoolModel).where(SchoolModel.id == student_update.school_id)
            if current_user_org_id:
                query = query.where(SchoolModel.organization_id == current_user_org_id)
                
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School not found or access denied")

        address_changed = False
        if student_update.address is not None:
            db_student.address = student_update.address
            lat, lng = await self._geocode_address(student_update.address)
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

    async def delete_student(self, student_id: str, current_user_org_id: Optional[str] = None):
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        if current_user_org_id:
            query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            
        db_student = (await self.db.execute(query)).scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")

        # Check attendance logs (RESTRICT via FK)
        query = select(func.count()).select_from(AttendanceLog).where(AttendanceLog.student_id == student_id)
        log_count = (await self.db.execute(query)).scalar()
        if log_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete student: {log_count} attendance log(s) reference it. Archive instead."
            )

        # parent_student_relations, student_bus_assignments, absences, notifications will CASCADE/SET NULL
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
            
            # Invalidate cache for each bus (pattern-based, C2 fix)
            for assignment in assignments:
                pattern = f"route:{assignment.bus_id}:*"
                await redis_manager.delete_pattern(pattern)
                logger.info(f"Route cache invalidated for bus {assignment.bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate route caches for student {student_id}: {str(e)}")
