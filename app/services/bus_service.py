from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional, Tuple

from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel
from ..database.models.user import User as UserModel
from ..database.models.bus_location import BusLocation
from ..database.models.student_bus_assignment import StudentBusAssignment
from ..database.models.attendance_log import AttendanceLog
from ..database.schemas.bus import BusCreate, BusUpdate

class BusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_buses(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
        school_id: Optional[str] = None
    ) -> Tuple[List[BusModel], int]:
        """
        Get buses with tenant filtering and total count.
        - Company Admin: Filter by Bus.organization_id
        - School Admin: Filter by Bus.school.organization_id
        """
        query = select(BusModel).options(
            selectinload(BusModel.current_driver),
            selectinload(BusModel.school)
        )
        count_query = select(func.count()).select_from(BusModel)
        
        # Tenant filter
        if current_user_org_id is not None:
            if current_user_org_type == "school":
                # School Admin -> Filter by Bus's School Organization
                query = query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
                count_query = count_query.join(SchoolModel).where(SchoolModel.organization_id == current_user_org_id)
            else:
                # Company Admin (default) -> Filter by Bus's Organization
                query = query.where(BusModel.organization_id == current_user_org_id)
                count_query = count_query.where(BusModel.organization_id == current_user_org_id)
            
        # Specific School Filter (Additional filter)
        if school_id:
            query = query.where(BusModel.school_id == school_id)
            count_query = count_query.where(BusModel.school_id == school_id)
        
        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_bus_by_id(self, bus_id: str) -> Optional[BusModel]:
        query = select(BusModel).options(
            selectinload(BusModel.current_driver),
            selectinload(BusModel.school)
        ).where(BusModel.id == bus_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_bus(self, bus: BusCreate, current_user_org_id: Optional[str] = None) -> BusModel:
        query = select(BusModel).where(BusModel.plate_number == bus.plate_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Plate number already exists")

        # Check tenant permission for school
        query = select(SchoolModel).where(SchoolModel.id == bus.school_id)
        if current_user_org_id:
            query = query.where(SchoolModel.organization_id == current_user_org_id)
            
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="School not found or access denied")

        if bus.current_driver_id:
            query = select(UserModel).where(UserModel.id == bus.current_driver_id)
            if current_user_org_id:
                query = query.where(UserModel.organization_id == current_user_org_id)
                
            driver = (await self.db.execute(query)).scalar_one_or_none()
            if not driver:
                raise HTTPException(status_code=400, detail="Driver not found or access denied")
            if driver.role.value != "sofor":
                raise HTTPException(status_code=400, detail="User is not a driver (sofor)")

        new_bus = BusModel(
            id=str(uuid4()),
            plate_number=bus.plate_number,
            capacity=bus.capacity,
            school_id=bus.school_id,
            organization_id=current_user_org_id, # Bus should belong to organization
            current_driver_id=bus.current_driver_id
        )
        self.db.add(new_bus)
        await self.db.commit()
        
        # Reload with relationships
        query = select(BusModel).options(
            selectinload(BusModel.current_driver),
            selectinload(BusModel.school)
        ).where(BusModel.id == new_bus.id)
        
        return (await self.db.execute(query)).scalar_one()

    async def update_bus(self, bus_id: str, bus_update: BusUpdate, current_user_org_id: Optional[str] = None) -> BusModel:
        query = select(BusModel).where(BusModel.id == bus_id)
        if current_user_org_id:
            query = query.where(BusModel.organization_id == current_user_org_id)
            
        db_bus = (await self.db.execute(query)).scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")

        if bus_update.plate_number and bus_update.plate_number != db_bus.plate_number:
            query = select(BusModel).where(BusModel.plate_number == bus_update.plate_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Plate number already exists")

        if bus_update.school_id:
            query = select(SchoolModel).where(SchoolModel.id == bus_update.school_id)
            if current_user_org_id:
                query = query.where(SchoolModel.organization_id == current_user_org_id)
                
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School not found or access denied")

        if bus_update.current_driver_id:
            query = select(UserModel).where(UserModel.id == bus_update.current_driver_id)
            if current_user_org_id:
                query = query.where(UserModel.organization_id == current_user_org_id)
                
            driver = (await self.db.execute(query)).scalar_one_or_none()
            if not driver:
                raise HTTPException(status_code=400, detail="Driver not found or access denied")
            if driver.role.value != "sofor":
                raise HTTPException(status_code=400, detail="User is not a driver (sofor)")

        if bus_update.plate_number is not None:
            db_bus.plate_number = bus_update.plate_number
        if bus_update.capacity is not None:
            db_bus.capacity = bus_update.capacity
        if bus_update.school_id is not None:
            db_bus.school_id = bus_update.school_id
        if bus_update.current_driver_id is not None:
            db_bus.current_driver_id = bus_update.current_driver_id

        await self.db.commit()
        
        # Reload with relationships
        query = select(BusModel).options(
            selectinload(BusModel.current_driver),
            selectinload(BusModel.school)
        ).where(BusModel.id == bus_id)
        
        return (await self.db.execute(query)).scalar_one()

    async def delete_bus(self, bus_id: str, current_user_org_id: Optional[str] = None):
        query = select(BusModel).where(BusModel.id == bus_id)
        if current_user_org_id:
            query = query.where(BusModel.organization_id == current_user_org_id)
            
        db_bus = (await self.db.execute(query)).scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")

        # Check for attendance logs referencing this bus (RESTRICT)
        query = select(func.count()).select_from(AttendanceLog).where(AttendanceLog.bus_id == bus_id)
        log_count = (await self.db.execute(query)).scalar()
        if log_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete bus: {log_count} attendance log(s) reference it. Archive instead."
            )

        # student_bus_assignments and bus_locations will CASCADE
        await self.db.delete(db_bus)
        await self.db.commit()

    async def get_bus_locations(self) -> List[BusLocation]:
        query = select(BusLocation).distinct(BusLocation.bus_id).order_by(BusLocation.bus_id, BusLocation.timestamp.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
