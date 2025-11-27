from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional

from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel
from ..database.models.user import User as UserModel
from ..database.models.bus_location import BusLocation
from ..database.schemas.bus import BusCreate, BusUpdate

class BusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_buses(self, skip: int = 0, limit: int = 100) -> List[BusModel]:
        query = select(BusModel).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_bus_by_id(self, bus_id: str) -> Optional[BusModel]:
        query = select(BusModel).where(BusModel.id == bus_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_bus(self, bus: BusCreate) -> BusModel:
        query = select(BusModel).where(BusModel.plate_number == bus.plate_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Plate number already exists")

        query = select(SchoolModel).where(SchoolModel.id == bus.school_id)
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="School not found")

        query = select(UserModel).where(UserModel.id == bus.current_driver_id)
        if not (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Driver not found")

        new_bus = BusModel(
            id=str(uuid4()),
            plate_number=bus.plate_number,
            capacity=bus.capacity,
            school_id=bus.school_id,
            current_driver_id=bus.current_driver_id
        )
        self.db.add(new_bus)
        await self.db.commit()
        await self.db.refresh(new_bus)
        return new_bus

    async def update_bus(self, bus_id: str, bus_update: BusUpdate) -> BusModel:
        db_bus = await self.get_bus_by_id(bus_id)
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found")

        if bus_update.plate_number and bus_update.plate_number != db_bus.plate_number:
            query = select(BusModel).where(BusModel.plate_number == bus_update.plate_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Plate number already exists")

        if bus_update.school_id:
            query = select(SchoolModel).where(SchoolModel.id == bus_update.school_id)
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School not found")

        if bus_update.current_driver_id:
            query = select(UserModel).where(UserModel.id == bus_update.current_driver_id)
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Driver not found")

        if bus_update.plate_number is not None:
            db_bus.plate_number = bus_update.plate_number
        if bus_update.capacity is not None:
            db_bus.capacity = bus_update.capacity
        if bus_update.school_id is not None:
            db_bus.school_id = bus_update.school_id
        if bus_update.current_driver_id is not None:
            db_bus.current_driver_id = bus_update.current_driver_id

        await self.db.commit()
        await self.db.refresh(db_bus)
        return db_bus

    async def delete_bus(self, bus_id: str):
        db_bus = await self.get_bus_by_id(bus_id)
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found")
        
        await self.db.delete(db_bus)
        await self.db.commit()

    async def get_bus_locations(self) -> List[BusLocation]:
        query = select(BusLocation).distinct(BusLocation.bus_id).order_by(BusLocation.bus_id, BusLocation.timestamp.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
