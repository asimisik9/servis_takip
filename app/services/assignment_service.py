from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
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

    async def assign_parent_to_student(
        self, 
        student_id: str, 
        parent_id: str,
        current_user_org_id: Optional[str] = None
    ) -> ParentStudentRelation:
        # Check student with tenant filter
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        if current_user_org_id:
            query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            
        student = (await self.db.execute(query)).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")
            
        # Check parent with tenant filter
        query = select(UserModel).where(UserModel.id == parent_id)
        if current_user_org_id:
            query = query.where(UserModel.organization_id == current_user_org_id)
            
        parent = (await self.db.execute(query)).scalar_one_or_none()
        if not parent or parent.role.value != "veli":
            raise HTTPException(status_code=400, detail="Parent not found, role is not veli, or access denied")
            
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
        
        # Reload with relationships
        query = select(ParentStudentRelation).options(
            selectinload(ParentStudentRelation.student).selectinload(StudentModel.school),
            selectinload(ParentStudentRelation.parent)
        ).where(ParentStudentRelation.id == new_relation.id)
        
        return (await self.db.execute(query)).scalar_one()

    async def assign_bus_to_student(
        self, 
        student_id: str, 
        bus_id: str,
        current_user_org_id: Optional[str] = None
    ) -> StudentBusAssignment:
        # Check student with tenant filter
        query = select(StudentModel).options(selectinload(StudentModel.school)).where(StudentModel.id == student_id)
        if current_user_org_id:
            query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            
        student = (await self.db.execute(query)).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found or access denied")
            
        # Check bus and get capacity with tenant filter
        query = select(BusModel).where(BusModel.id == bus_id)
        if current_user_org_id:
            query = query.where(BusModel.organization_id == current_user_org_id)
            
        bus = (await self.db.execute(query)).scalar_one_or_none()
        if not bus:
            raise HTTPException(status_code=400, detail="Bus not found or access denied")
            
        # Business Logic: School Match Validation
        if student.school_id != bus.school_id:
            raise HTTPException(
                status_code=400, 
                detail="Student and Bus must belong to the same school"
            )
            
        # Check existence
        query = select(StudentBusAssignment).where(
            StudentBusAssignment.student_id == student_id,
            StudentBusAssignment.bus_id == bus_id
        )
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Assignment already exists")

        # Bus capacity enforcement
        query = select(func.count()).select_from(StudentBusAssignment).where(
            StudentBusAssignment.bus_id == bus_id
        )
        # Using separate connection for locking would be better but for now simple check
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
        
        # Reload with relationships to avoid MissingGreenlet error
        query = select(StudentBusAssignment).options(
            selectinload(StudentBusAssignment.student).selectinload(StudentModel.school),
            selectinload(StudentBusAssignment.bus)
        ).where(StudentBusAssignment.id == new_assignment.id)
        
        loaded_assignment = (await self.db.execute(query)).scalar_one()

        # Invalidate route cache for this bus
        await self._invalidate_route_cache(bus_id)

        return loaded_assignment

    async def assign_driver_to_bus(
        self, 
        bus_id: str, 
        driver_id: str,
        current_user_org_id: Optional[str] = None
    ) -> BusModel:
        query = select(BusModel).where(BusModel.id == bus_id)
        if current_user_org_id:
            query = query.where(BusModel.organization_id == current_user_org_id)
            
        bus = (await self.db.execute(query)).scalar_one_or_none()
        if not bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")
            
        query = select(UserModel).where(UserModel.id == driver_id)
        if current_user_org_id:
            query = query.where(UserModel.organization_id == current_user_org_id)
            
        driver = (await self.db.execute(query)).scalar_one_or_none()
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
        current_user_org_type: Optional[str] = None
    ) -> Tuple[List[StudentBusAssignment], int]:
        """
        Get student bus assignments with tenant filtering.
        - Company Admin: Filter by Bus.organization_id
        - School Admin: Filter by Student.school.organization_id
        """
        query = select(StudentBusAssignment).options(
            selectinload(StudentBusAssignment.student).selectinload(StudentModel.school),
            selectinload(StudentBusAssignment.bus)
        )
        count_query = select(func.count()).select_from(StudentBusAssignment)
        
        # Tenant filter
        if current_user_org_id is not None:
            if current_user_org_type == "school":
                # School Admin -> Filter by Student's School
                query = query.join(StudentModel).join(SchoolModel).where(
                    SchoolModel.organization_id == current_user_org_id
                )
                count_query = count_query.join(StudentModel).join(SchoolModel).where(
                    SchoolModel.organization_id == current_user_org_id
                )
            else:
                # Company Admin (default) -> Filter by Bus's Company
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
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None
    ) -> Tuple[List[ParentStudentRelation], int]:
        """
        Get parent-student relations with tenant filtering.
        - School Admin: Filter by Student.school.organization_id
        - Company Admin: Filter by Student assigned to one of my buses
        """
        query = select(ParentStudentRelation).options(
            selectinload(ParentStudentRelation.student).selectinload(StudentModel.school),
            selectinload(ParentStudentRelation.parent)
        )
        count_query = select(func.count()).select_from(ParentStudentRelation)
        
        # Tenant filter
        if current_user_org_id is not None:
            if current_user_org_type == "transport_company":
                # Company Admin -> Filter relations where student is assigned to my bus
                # Join: Relation -> Student -> StudentBusAssignment -> Bus
                query = query.join(ParentStudentRelation.student)\
                             .join(StudentBusAssignment)\
                             .join(BusModel)\
                             .where(BusModel.organization_id == current_user_org_id)
                
                count_query = count_query.join(ParentStudentRelation.student)\
                                         .join(StudentBusAssignment)\
                                         .join(BusModel)\
                                         .where(BusModel.organization_id == current_user_org_id)
            else:
                # School Admin (default) -> Filter by Student's School
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

    async def delete_student_bus_assignment(self, assignment_id: str, current_user_org_id: Optional[str] = None):
        query = select(StudentBusAssignment).options(selectinload(StudentBusAssignment.bus)).where(StudentBusAssignment.id == assignment_id)
        if current_user_org_id:
            query = query.join(BusModel).where(BusModel.organization_id == current_user_org_id)
            
        assignment = (await self.db.execute(query)).scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found or access denied")
        
        bus_id = assignment.bus_id
        await self.db.delete(assignment)
        await self.db.commit()
        
        # Invalidate route cache for this bus
        await self._invalidate_route_cache(bus_id)

    async def delete_parent_student_relation(self, relation_id: str, current_user_org_id: Optional[str] = None):
        query = select(ParentStudentRelation).options(
            selectinload(ParentStudentRelation.student).selectinload(StudentModel.school)
        ).where(ParentStudentRelation.id == relation_id)
        
        if current_user_org_id:
            query = query.join(StudentModel).join(SchoolModel).where(
                SchoolModel.organization_id == current_user_org_id
            )
            
        relation = (await self.db.execute(query)).scalar_one_or_none()
        if not relation:
            raise HTTPException(status_code=404, detail="Relation not found or access denied")
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
