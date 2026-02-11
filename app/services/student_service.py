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
from ..database.models.organization import Organization as OrganizationModel
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

    async def _ensure_organization_exists(self, organization_id: str) -> None:
        organization = await self.db.get(OrganizationModel, organization_id)
        if not organization:
            raise HTTPException(status_code=400, detail="Organization not found")

    async def _ensure_school_exists(self, school_id: str) -> None:
        school = await self.db.get(SchoolModel, school_id)
        if not school:
            raise HTTPException(status_code=400, detail="School not found")

    async def get_students(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        school_id: Optional[str] = None,
        organization_filter: Optional[str] = None,
    ) -> Tuple[List[StudentModel], int]:
        """
        Get students with tenant filtering and total count.
        current_user_org_id: tenant admin scope
        organization_filter: optional super-admin filter by organization_id
        Returns: (students, total_count)
        """
        query = select(StudentModel).options(
            selectinload(StudentModel.school),
            selectinload(StudentModel.organization),
        )
        count_query = select(func.count()).select_from(StudentModel)

        if current_user_org_id is not None:
            query = query.where(StudentModel.organization_id == current_user_org_id)
            count_query = count_query.where(StudentModel.organization_id == current_user_org_id)
        elif organization_filter is not None:
            query = query.where(StudentModel.organization_id == organization_filter)
            count_query = count_query.where(StudentModel.organization_id == organization_filter)

        if school_id:
            query = query.where(StudentModel.school_id == school_id)
            count_query = count_query.where(StudentModel.school_id == school_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_student_by_id(self, student_id: str) -> Optional[StudentModel]:
        query = (
            select(StudentModel)
            .options(selectinload(StudentModel.school), selectinload(StudentModel.organization))
            .where(StudentModel.id == student_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_student(self, student: StudentCreate, current_user_org_id: Optional[str] = None) -> StudentModel:
        query = select(StudentModel).where(StudentModel.student_number == student.student_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Student number already exists")

        organization_id = current_user_org_id if current_user_org_id is not None else student.organization_id
        if not organization_id:
            raise HTTPException(
                status_code=400,
                detail="organization_id is required for student creation",
            )

        await self._ensure_organization_exists(organization_id)

        if student.school_id is not None:
            await self._ensure_school_exists(student.school_id)

        lat, lng = None, None
        if student.address:
            lat, lng = await self._geocode_address(student.address)

        new_student = StudentModel(
            id=str(uuid4()),
            full_name=student.full_name,
            student_number=student.student_number,
            school_id=student.school_id,
            organization_id=organization_id,
            address=student.address,
            latitude=lat,
            longitude=lng,
        )
        self.db.add(new_student)
        await self.db.commit()
        await self.db.refresh(new_student)
        return await self.get_student_by_id(new_student.id)

    async def update_student(
        self,
        student_id: str,
        student_update: StudentUpdate,
        current_user_org_id: Optional[str] = None,
    ) -> StudentModel:
        query = (
            select(StudentModel)
            .options(selectinload(StudentModel.school), selectinload(StudentModel.organization))
            .where(StudentModel.id == student_id)
        )
        if current_user_org_id:
            query = query.where(StudentModel.organization_id == current_user_org_id)

        db_student = (await self.db.execute(query)).scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")

        if student_update.student_number and student_update.student_number != db_student.student_number:
            query = select(StudentModel).where(StudentModel.student_number == student_update.student_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Student number already exists")

        if current_user_org_id is not None:
            target_organization_id = current_user_org_id
        elif "organization_id" in student_update.model_fields_set:
            target_organization_id = student_update.organization_id
        else:
            target_organization_id = db_student.organization_id

        if not target_organization_id:
            raise HTTPException(
                status_code=400,
                detail="organization_id cannot be empty for students",
            )
        await self._ensure_organization_exists(target_organization_id)

        if "school_id" in student_update.model_fields_set and student_update.school_id is not None:
            await self._ensure_school_exists(student_update.school_id)

        address_changed = False
        if "address" in student_update.model_fields_set:
            db_student.address = student_update.address
            if student_update.address:
                lat, lng = await self._geocode_address(student_update.address)
                db_student.latitude = lat
                db_student.longitude = lng
            else:
                db_student.latitude = None
                db_student.longitude = None
            address_changed = True

        if student_update.full_name is not None:
            db_student.full_name = student_update.full_name
        if student_update.student_number is not None:
            db_student.student_number = student_update.student_number
        if "school_id" in student_update.model_fields_set:
            db_student.school_id = student_update.school_id

        if current_user_org_id is not None:
            db_student.organization_id = current_user_org_id
        elif "organization_id" in student_update.model_fields_set:
            db_student.organization_id = student_update.organization_id

        await self.db.commit()
        await self.db.refresh(db_student)

        if address_changed:
            await self._invalidate_route_caches_for_student(student_id)

        return await self.get_student_by_id(db_student.id)

    async def delete_student(self, student_id: str, current_user_org_id: Optional[str] = None):
        query = (
            select(StudentModel)
            .options(selectinload(StudentModel.school), selectinload(StudentModel.organization))
            .where(StudentModel.id == student_id)
        )
        if current_user_org_id:
            query = query.where(StudentModel.organization_id == current_user_org_id)

        db_student = (await self.db.execute(query)).scalar_one_or_none()
        if not db_student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")

        query = select(func.count()).select_from(AttendanceLog).where(AttendanceLog.student_id == student_id)
        log_count = (await self.db.execute(query)).scalar()
        if log_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete student: {log_count} attendance log(s) reference it. Archive instead.",
            )

        await self.db.delete(db_student)
        await self.db.commit()

    async def _invalidate_route_caches_for_student(self, student_id: str) -> None:
        """Invalidate route caches for all buses that have this student assigned"""
        try:
            query = select(StudentBusAssignment).where(StudentBusAssignment.student_id == student_id)
            result = await self.db.execute(query)
            assignments = result.scalars().all()

            for assignment in assignments:
                pattern = f"route:{assignment.bus_id}:*"
                await redis_manager.delete_pattern(pattern)
                logger.info(f"Route cache invalidated for bus {assignment.bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate route caches for student {student_id}: {str(e)}")
