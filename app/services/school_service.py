from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional

from ..database.models.school import School as SchoolModel
from ..database.models.user import User as UserModel
from ..database.schemas.school import SchoolCreate, SchoolUpdate

class SchoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_schools(self, skip: int = 0, limit: int = 100) -> List[SchoolModel]:
        query = select(SchoolModel).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_school_by_id(self, school_id: str) -> Optional[SchoolModel]:
        query = select(SchoolModel).where(SchoolModel.id == school_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_school(self, school: SchoolCreate) -> SchoolModel:
        query = select(SchoolModel).where(SchoolModel.school_name == school.school_name)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="School name already exists")

        new_school = SchoolModel(
            id=str(uuid4()),
            school_name=school.school_name,
            school_address=school.school_address,
            contact_person_id=school.contact_person_id
        )
        self.db.add(new_school)
        await self.db.commit()
        await self.db.refresh(new_school)
        return new_school

    async def update_school(self, school_id: str, school_update: SchoolUpdate) -> SchoolModel:
        db_school = await self.get_school_by_id(school_id)
        if not db_school:
            raise HTTPException(status_code=404, detail="School not found")

        if school_update.school_name and school_update.school_name != db_school.school_name:
            query = select(SchoolModel).where(SchoolModel.school_name == school_update.school_name)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School name already exists")

        if school_update.contact_person_id:
            query = select(UserModel).where(UserModel.id == school_update.contact_person_id)
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Contact person not found")

        if school_update.school_name is not None:
            db_school.school_name = school_update.school_name
        if school_update.school_address is not None:
            db_school.school_address = school_update.school_address
        if school_update.contact_person_id is not None:
            db_school.contact_person_id = school_update.contact_person_id

        await self.db.commit()
        await self.db.refresh(db_school)
        return db_school

    async def delete_school(self, school_id: str):
        db_school = await self.get_school_by_id(school_id)
        if not db_school:
            raise HTTPException(status_code=404, detail="School not found")
        
        await self.db.delete(db_school)
        await self.db.commit()
