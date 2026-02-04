from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional
import googlemaps
import logging

from ..core.config import settings
from ..database.models.school import School as SchoolModel
from ..database.models.user import User as UserModel
from ..database.schemas.school import SchoolCreate, SchoolUpdate

logger = logging.getLogger(__name__)

class SchoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _geocode_address(self, address: str) -> tuple[Optional[float], Optional[float]]:
        """Convert address to latitude and longitude using Google Maps API"""
        if not settings.GOOGLE_MAPS_API_KEY:
            logger.warning("GOOGLE_MAPS_API_KEY not configured, skipping geocoding")
            return None, None
        
        gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        try:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lng = location['lat'], location['lng']
                logger.info(f"Geocoded school address '{address}' -> ({lat}, {lng})")
                return lat, lng
            else:
                logger.warning(f"No geocode result for school address: {address}")
        except Exception as e:
            logger.error(f"Geocoding error for school address '{address}': {e}")
        return None, None

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

        # Geocode the school address
        lat, lng = self._geocode_address(school.school_address)

        new_school = SchoolModel(
            id=str(uuid4()),
            school_name=school.school_name,
            school_address=school.school_address,
            contact_person_id=school.contact_person_id,
            latitude=lat,
            longitude=lng
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
        
        # If address is updated, re-geocode
        if school_update.school_address is not None and school_update.school_address != db_school.school_address:
            db_school.school_address = school_update.school_address
            lat, lng = self._geocode_address(school_update.school_address)
            db_school.latitude = lat
            db_school.longitude = lng
            logger.info(f"Updated school {school_id} coordinates to ({lat}, {lng})")
        
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

    async def geocode_existing_schools(self) -> dict:
        """Geocode all schools that don't have coordinates yet"""
        query = select(SchoolModel).where(
            (SchoolModel.latitude.is_(None)) | (SchoolModel.longitude.is_(None))
        )
        result = await self.db.execute(query)
        schools = result.scalars().all()
        
        updated = 0
        failed = 0
        for school in schools:
            if school.school_address:
                lat, lng = self._geocode_address(school.school_address)
                if lat is not None and lng is not None:
                    school.latitude = lat
                    school.longitude = lng
                    updated += 1
                else:
                    failed += 1
        
        await self.db.commit()
        logger.info(f"Geocoded {updated} schools, {failed} failed")
        return {"updated": updated, "failed": failed, "total": len(schools)}
