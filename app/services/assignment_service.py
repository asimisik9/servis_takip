import logging
from typing import List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.redis import redis_manager
from ..database.models.bus import Bus as BusModel
from ..database.models.parent_student_relation import ParentStudentRelation
from ..database.models.student import Student as StudentModel
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.user import User as UserModel

logger = logging.getLogger(__name__)


class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_student_with_scope(
        self,
        student_id: str,
        current_user_org_id: Optional[str],
        current_user_org_type: Optional[str],
    ) -> StudentModel:
        query = (
            select(StudentModel)
            .options(selectinload(StudentModel.school), selectinload(StudentModel.organization))
            .where(StudentModel.id == student_id)
        )
        if current_user_org_id:
            query = query.where(StudentModel.organization_id == current_user_org_id)

        student = (await self.db.execute(query)).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")
        return student

    async def _get_bus_with_scope(
        self,
        bus_id: str,
        current_user_org_id: Optional[str],
        current_user_org_type: Optional[str],
    ) -> BusModel:
        query = select(BusModel).where(BusModel.id == bus_id)
        if current_user_org_id:
            query = query.where(BusModel.organization_id == current_user_org_id)

        bus = (await self.db.execute(query)).scalar_one_or_none()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")
        return bus

    async def assign_parent_to_student(
        self,
        student_id: str,
        parent_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> ParentStudentRelation:
        student = await self._get_student_with_scope(
            student_id,
            current_user_org_id=current_user_org_id,
            current_user_org_type=current_user_org_type,
        )

        parent_query = select(UserModel).where(UserModel.id == parent_id)
        if student.organization_id is not None:
            parent_query = parent_query.where(UserModel.organization_id == student.organization_id)
        parent = (await self.db.execute(parent_query)).scalar_one_or_none()
        if not parent or parent.role.value != "veli":
            raise HTTPException(status_code=400, detail="Parent not found, role is not veli, or access denied")

        if parent.organization_id != student.organization_id:
            raise HTTPException(
                status_code=400,
                detail="Parent and Student must belong to the same organization",
            )

        relation_query = select(ParentStudentRelation).where(
            ParentStudentRelation.student_id == student.id,
            ParentStudentRelation.parent_id == parent_id,
        )
        if (await self.db.execute(relation_query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Relation already exists")

        new_relation = ParentStudentRelation(
            id=str(uuid4()),
            student_id=student.id,
            parent_id=parent_id,
        )
        self.db.add(new_relation)
        await self.db.commit()

        reload_query = (
            select(ParentStudentRelation)
            .options(
                selectinload(ParentStudentRelation.student).selectinload(StudentModel.school),
                selectinload(ParentStudentRelation.parent),
            )
            .where(ParentStudentRelation.id == new_relation.id)
        )
        return (await self.db.execute(reload_query)).scalar_one()

    async def assign_bus_to_student(
        self,
        student_id: str,
        bus_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> StudentBusAssignment:
        student = await self._get_student_with_scope(
            student_id,
            current_user_org_id=current_user_org_id,
            current_user_org_type=current_user_org_type,
        )
        bus = await self._get_bus_with_scope(
            bus_id,
            current_user_org_id=current_user_org_id,
            current_user_org_type=current_user_org_type,
        )

        if (
            student.organization_id is None
            or bus.organization_id is None
            or student.organization_id != bus.organization_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Student and Bus must belong to the same organization",
            )

        if student.school_id and student.school_id != bus.school_id:
            raise HTTPException(
                status_code=400,
                detail="Student and Bus must belong to the same school when student has school_id",
            )

        exists_query = select(StudentBusAssignment).where(
            StudentBusAssignment.student_id == student_id,
            StudentBusAssignment.bus_id == bus_id,
        )
        if (await self.db.execute(exists_query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Assignment already exists")

        count_query = select(func.count()).select_from(StudentBusAssignment).where(
            StudentBusAssignment.bus_id == bus_id
        )
        current_count = (await self.db.execute(count_query)).scalar() or 0
        if current_count >= bus.capacity:
            raise HTTPException(
                status_code=409,
                detail=f"Bus is full ({current_count}/{bus.capacity}). Cannot assign more students.",
            )

        new_assignment = StudentBusAssignment(
            id=str(uuid4()),
            student_id=student_id,
            bus_id=bus_id,
        )
        self.db.add(new_assignment)
        await self.db.commit()

        reload_query = (
            select(StudentBusAssignment)
            .options(
                selectinload(StudentBusAssignment.student).selectinload(StudentModel.school),
                selectinload(StudentBusAssignment.bus),
            )
            .where(StudentBusAssignment.id == new_assignment.id)
        )
        loaded_assignment = (await self.db.execute(reload_query)).scalar_one()

        await self._invalidate_route_cache(bus_id)
        return loaded_assignment

    async def assign_driver_to_bus(
        self,
        bus_id: str,
        driver_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> BusModel:
        bus = await self._get_bus_with_scope(
            bus_id,
            current_user_org_id=current_user_org_id,
            current_user_org_type=current_user_org_type,
        )

        driver_query = select(UserModel).where(UserModel.id == driver_id)
        if bus.organization_id:
            driver_query = driver_query.where(UserModel.organization_id == bus.organization_id)
        driver = (await self.db.execute(driver_query)).scalar_one_or_none()
        if not driver or driver.role.value != "sofor":
            raise HTTPException(status_code=400, detail="Driver not found, role is not sofor, or access denied")

        bus.current_driver_id = driver_id
        await self.db.commit()
        await self.db.refresh(bus)
        return bus

    async def get_student_bus_assignments(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
        organization_filter: Optional[str] = None,
    ) -> Tuple[List[StudentBusAssignment], int]:
        query = select(StudentBusAssignment).options(
            selectinload(StudentBusAssignment.student).selectinload(StudentModel.school),
            selectinload(StudentBusAssignment.bus),
        )
        count_query = select(func.count()).select_from(StudentBusAssignment)

        if current_user_org_id is not None:
            query = query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)
            count_query = count_query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)
        elif organization_filter is not None:
            query = query.join(StudentModel).where(StudentModel.organization_id == organization_filter)
            count_query = count_query.join(StudentModel).where(StudentModel.organization_id == organization_filter)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_parent_student_relations(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
        organization_filter: Optional[str] = None,
    ) -> Tuple[List[ParentStudentRelation], int]:
        query = select(ParentStudentRelation).options(
            selectinload(ParentStudentRelation.student).selectinload(StudentModel.school),
            selectinload(ParentStudentRelation.parent),
        )
        count_query = select(func.count()).select_from(ParentStudentRelation)

        if current_user_org_id is not None:
            query = query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)
            count_query = count_query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)
        elif organization_filter is not None:
            query = query.join(StudentModel).where(StudentModel.organization_id == organization_filter)
            count_query = count_query.join(StudentModel).where(StudentModel.organization_id == organization_filter)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def delete_student_bus_assignment(
        self,
        assignment_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ):
        query = (
            select(StudentBusAssignment)
            .options(selectinload(StudentBusAssignment.bus), selectinload(StudentBusAssignment.student))
            .where(StudentBusAssignment.id == assignment_id)
        )
        if current_user_org_id:
            query = query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)

        assignment = (await self.db.execute(query)).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found or access denied")

        bus_id = assignment.bus_id
        await self.db.delete(assignment)
        await self.db.commit()
        await self._invalidate_route_cache(bus_id)

    async def delete_parent_student_relation(
        self,
        relation_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ):
        query = (
            select(ParentStudentRelation)
            .options(selectinload(ParentStudentRelation.student).selectinload(StudentModel.school))
            .where(ParentStudentRelation.id == relation_id)
        )

        if current_user_org_id:
            query = query.join(StudentModel).where(StudentModel.organization_id == current_user_org_id)

        relation = (await self.db.execute(query)).scalar_one_or_none()
        if not relation:
            raise HTTPException(status_code=404, detail="Relation not found or access denied")
        await self.db.delete(relation)
        await self.db.commit()

    async def _invalidate_route_cache(self, bus_id: str) -> None:
        try:
            pattern = f"route:{bus_id}:*"
            await redis_manager.delete_pattern(pattern)
            logger.info(f"Route cache invalidated for bus {bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for bus {bus_id}: {str(e)}")
