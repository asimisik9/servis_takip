from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional, Tuple
import httpx
import logging

from ..core.config import settings
from ..database.models.school import School as SchoolModel
from ..database.models.organization import Organization as OrganizationModel, OrganizationType
from ..database.models.user import User as UserModel
from ..database.models.student import Student as StudentModel
from ..database.models.bus import Bus as BusModel
from ..database.schemas.school import SchoolCreate, SchoolUpdate

logger = logging.getLogger(__name__)

class SchoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _validate_school_organization(self, organization_id: str) -> OrganizationModel:
        """School records must always be attached to a school-type organization."""
        query = select(OrganizationModel).where(OrganizationModel.id == organization_id)
        organization = (await self.db.execute(query)).scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=400, detail="Organization not found")
        if organization.type != OrganizationType.school:
            raise HTTPException(
                status_code=400,
                detail="School organization must be of type 'school'"
            )
        if not organization.is_active:
            raise HTTPException(status_code=400, detail="Organization is inactive")
        return organization

    async def _geocode_address(self, address: str) -> tuple[Optional[float], Optional[float]]:
        """Convert address to latitude and longitude using Google Maps Geocoding API (async)"""
        if not settings.GOOGLE_MAPS_API_KEY:
            logger.warning("GOOGLE_MAPS_API_KEY not configured, skipping geocoding")
            return None, None
        
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": settings.GOOGLE_MAPS_API_KEY}
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                result = response.json()
            
            if result.get("status") == "OK" and result.get("results"):
                location = result["results"][0]["geometry"]["location"]
                lat, lng = location["lat"], location["lng"]
                logger.info(f"Geocoded school address '{address}' -> ({lat}, {lng})")
                return lat, lng
            else:
                logger.warning(f"No geocode result for school address: {address} (status: {result.get('status')})")
        except Exception as e:
            logger.error(f"Geocoding error for school address '{address}': {e}")
        return None, None

    async def get_schools(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None
    ) -> Tuple[List[SchoolModel], int]:
        """
        Get schools with tenant filtering and total count.
        Returns: (schools, total_count)
        """
        query = select(SchoolModel).options(selectinload(SchoolModel.contact_person))
        count_query = select(func.count()).select_from(SchoolModel)
        
        # Tenant filter
        if current_user_org_id is not None:
            query = query.where(SchoolModel.organization_id == current_user_org_id)
            count_query = count_query.where(SchoolModel.organization_id == current_user_org_id)
        
        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_school_by_id(
        self,
        school_id: str,
        current_user_org_id: Optional[str] = None
    ) -> Optional[SchoolModel]:
        query = select(SchoolModel).options(
            selectinload(SchoolModel.contact_person)
        ).where(SchoolModel.id == school_id)
        if current_user_org_id is not None:
            query = query.where(SchoolModel.organization_id == current_user_org_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_school(
        self,
        school: SchoolCreate,
        current_user_org_id: Optional[str] = None
    ) -> SchoolModel:
        query = select(SchoolModel).where(SchoolModel.school_name == school.school_name)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="School name already exists")

        # Validate contact person exists
        contact_person = None
        if school.contact_person_id:
            query = select(UserModel).where(UserModel.id == school.contact_person_id)
            if current_user_org_id:
                query = query.where(UserModel.organization_id == current_user_org_id)
            contact_person = (await self.db.execute(query)).scalar_one_or_none()
            if not contact_person:
                raise HTTPException(status_code=400, detail="Contact person not found or access denied")

        organization_id = current_user_org_id

        # Super admin flow: infer organization from contact person.
        if organization_id is None:
            organization_id = contact_person.organization_id if contact_person else None
            if organization_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="School organization could not be inferred. Provide a contact person in target organization."
                )

        await self._validate_school_organization(organization_id)

        if contact_person and contact_person.organization_id != organization_id:
            raise HTTPException(
                status_code=400,
                detail="Contact person must belong to the school's organization"
            )

        # Geocode the school address
        lat, lng = await self._geocode_address(school.school_address)

        new_school = SchoolModel(
            id=str(uuid4()),
            school_name=school.school_name,
            school_address=school.school_address,
            contact_person_id=school.contact_person_id,
            organization_id=organization_id,
            latitude=lat,
            longitude=lng
        )
        self.db.add(new_school)
        await self.db.commit()
        await self.db.refresh(new_school)
        return new_school

    async def update_school(
        self,
        school_id: str,
        school_update: SchoolUpdate,
        current_user_org_id: Optional[str] = None
    ) -> SchoolModel:
        db_school = await self.get_school_by_id(school_id, current_user_org_id=current_user_org_id)
        if not db_school:
            raise HTTPException(status_code=404, detail="School not found")

        if school_update.school_name and school_update.school_name != db_school.school_name:
            query = select(SchoolModel).where(SchoolModel.school_name == school_update.school_name)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="School name already exists")

        if school_update.contact_person_id:
            query = select(UserModel).where(
                UserModel.id == school_update.contact_person_id,
                UserModel.organization_id == db_school.organization_id
            )
            if not (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Contact person not found or access denied")

        if school_update.school_name is not None:
            db_school.school_name = school_update.school_name
        
        # If address is updated, re-geocode
        if school_update.school_address is not None and school_update.school_address != db_school.school_address:
            db_school.school_address = school_update.school_address
            lat, lng = await self._geocode_address(school_update.school_address)
            db_school.latitude = lat
            db_school.longitude = lng
            logger.info(f"Updated school {school_id} coordinates to ({lat}, {lng})")
        
        if school_update.contact_person_id is not None:
            db_school.contact_person_id = school_update.contact_person_id

        await self.db.commit()
        await self.db.refresh(db_school)
        return db_school

    async def delete_school(self, school_id: str, current_user_org_id: Optional[str] = None):
        db_school = await self.get_school_by_id(school_id, current_user_org_id=current_user_org_id)
        if not db_school:
            raise HTTPException(status_code=404, detail="School not found")

        # Check students referencing this school (RESTRICT)
        query = select(func.count()).select_from(StudentModel).where(StudentModel.school_id == school_id)
        student_count = (await self.db.execute(query)).scalar()
        if student_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete school: {student_count} student(s) belong to it. Reassign or remove them first."
            )

        # Check buses referencing this school (RESTRICT)
        query = select(func.count()).select_from(BusModel).where(BusModel.school_id == school_id)
        bus_count = (await self.db.execute(query)).scalar()
        if bus_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete school: {bus_count} bus(es) belong to it. Reassign or remove them first."
            )

        await self.db.delete(db_school)
        await self.db.commit()

    async def geocode_existing_schools(self, current_user_org_id: Optional[str] = None) -> dict:
        """Geocode all schools that don't have coordinates yet"""
        query = select(SchoolModel).where(
            (SchoolModel.latitude.is_(None)) | (SchoolModel.longitude.is_(None))
        )
        if current_user_org_id is not None:
            query = query.where(SchoolModel.organization_id == current_user_org_id)
        result = await self.db.execute(query)
        schools = result.scalars().all()
        
        updated = 0
        failed = 0
        for school in schools:
            if school.school_address:
                lat, lng = await self._geocode_address(school.school_address)
                if lat is not None and lng is not None:
                    school.latitude = lat
                    school.longitude = lng
                    updated += 1
                else:
                    failed += 1
        
        await self.db.commit()
        logger.info(f"Geocoded {updated} schools, {failed} failed")
        return {"updated": updated, "failed": failed, "total": len(schools)}
