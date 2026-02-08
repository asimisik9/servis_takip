from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional, Tuple
import logging

from ..database.models.student import Student as StudentModel
from ..database.models.user import User as UserModel
from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel
from ..database.models.parent_student_relation import ParentStudentRelation
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)

class AssignmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assign_parent_to_student(self, student_id: str, parent_id: str) -> ParentStudentRelation:
        # Check student
        query = select(StudentModel).where(StudentModel.id == student_id)
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found")
            
        # Check parent
        query = select(UserModel).where(UserModel.id == parent_id)
        parent = (await self.db.execute(query)).scalar_one_or_none()
        if not parent or parent.role.value != "veli":
            raise HTTPException(status_code=400, detail="Parent not found or role is not veli")
            
        # Check existence
        query = select(ParentStudentRelation).where(
            ParentStudentRelation.student_id == student_id,
            ParentStudentRelation.parent_id == parent_id
        )
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Relation already exists")
            
        new_relation = ParentStudentRelation(
            id=str(uuid4()),
            student_id=student_id,
            parent_id=parent_id
        )
        self.db.add(new_relation)
        await self.db.commit()
        await self.db.refresh(new_relation)
        return new_relation

    async def assign_bus_to_student(self, student_id: str, bus_id: str) -> StudentBusAssignment:
        # Check student
        query = select(StudentModel).where(StudentModel.id == student_id)
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Student not found")
            
        # Check bus and get capacity
        query = select(BusModel).where(BusModel.id == bus_id)
        bus = (await self.db.execute(query)).scalar_one_or_none()
        if not bus:
            raise HTTPException(status_code=400, detail="Bus not found")
            
        # Check existence
        query = select(StudentBusAssignment).where(
            StudentBusAssignment.student_id == student_id,
            StudentBusAssignment.bus_id == bus_id
        )
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Assignment already exists")

        # H6: Bus capacity enforcement
        query = select(func.count()).select_from(StudentBusAssignment).where(
            StudentBusAssignment.bus_id == bus_id
        )
        current_count = (await self.db.execute(query)).scalar()
        if current_count >= bus.capacity:
            raise HTTPException(
                status_code=409,
                detail=f"Bus is full ({current_count}/{bus.capacity}). Cannot assign more students."
            )
            
        new_assignment = StudentBusAssignment(
            id=str(uuid4()),
            student_id=student_id,
            bus_id=bus_id
        )
        self.db.add(new_assignment)
        await self.db.commit()
        await self.db.refresh(new_assignment)
        
        # Invalidate route cache for this bus
        await self._invalidate_route_cache(bus_id)
        
        return new_assignment

    async def assign_driver_to_bus(self, bus_id: str, driver_id: str) -> BusModel:
        query = select(BusModel).where(BusModel.id == bus_id)
        bus = (await self.db.execute(query)).scalar_one_or_none()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found")
            
        query = select(UserModel).where(UserModel.id == driver_id)
        driver = (await self.db.execute(query)).scalar_one_or_none()
        if not driver or driver.role.value != "sofor":
            raise HTTPException(status_code=400, detail="Driver not found or role is not sofor")
            
        bus.current_driver_id = driver_id
        await self.db.commit()
        await self.db.refresh(bus)
        return bus

    async def get_student_bus_assignments(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None
    ) -> Tuple[List[StudentBusAssignment], int]:
        """
        Get student bus assignments with tenant filtering.
        Filters by bus's organization_id.
        Returns: (assignments, total_count)
        """
        query = select(StudentBusAssignment)
        count_query = select(func.count()).select_from(StudentBusAssignment)
        
        # Tenant filter - join with bus to filter by org
        if current_user_org_id is not None:
            query = query.join(BusModel).where(BusModel.organization_id == current_user_org_id)
            count_query = count_query.join(BusModel).where(BusModel.organization_id == current_user_org_id)
        
        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_parent_student_relations(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None
    ) -> Tuple[List[ParentStudentRelation], int]:
        """
        Get parent-student relations with tenant filtering.
        Filters by student's school's organization_id.
        Returns: (relations, total_count)
        """
        query = select(ParentStudentRelation)
        count_query = select(func.count()).select_from(ParentStudentRelation)
        
        # Tenant filter - join student -> school to filter by org
        if current_user_org_id is not None:
            query = query.join(StudentModel).join(SchoolModel).where(
                SchoolModel.organization_id == current_user_org_id
            )
            count_query = count_query.join(StudentModel).join(SchoolModel).where(
                SchoolModel.organization_id == current_user_org_id
            )
        
        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def delete_student_bus_assignment(self, assignment_id: str):
        query = select(StudentBusAssignment).where(StudentBusAssignment.id == assignment_id)
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        bus_id = assignment.bus_id
        await self.db.delete(assignment)
        await self.db.commit()
        
        # Invalidate route cache for this bus
        await self._invalidate_route_cache(bus_id)

    async def delete_parent_student_relation(self, relation_id: str):
        query = select(ParentStudentRelation).where(ParentStudentRelation.id == relation_id)
        relation = (await self.db.execute(query)).scalar_one_or_none()
        if not relation:
            raise HTTPException(status_code=404, detail="Relation not found")
        await self.db.delete(relation)
        await self.db.commit()
    
    async def _invalidate_route_cache(self, bus_id: str) -> None:
        """Invalidate all cached routes for a bus (pattern-based)"""
        try:
            pattern = f"route:{bus_id}:*"
            await redis_manager.delete_pattern(pattern)
            logger.info(f"Route cache invalidated for bus {bus_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache for bus {bus_id}: {str(e)}")
