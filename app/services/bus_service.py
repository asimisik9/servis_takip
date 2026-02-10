from typing import List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.models.attendance_log import AttendanceLog
from ..database.models.bus import Bus as BusModel
from ..database.models.bus_location import BusLocation
from ..database.models.organization import Organization as OrganizationModel
from ..database.models.school import School as SchoolModel
from ..database.models.school_company_contract import SchoolCompanyContract as ContractModel
from ..database.models.user import User as UserModel
from ..database.schemas.bus import BusCreate, BusUpdate


class BusService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _apply_bus_scope(
        self,
        query,
        current_user_org_id: Optional[str],
        current_user_org_type: Optional[str],
    ):
        if current_user_org_id is None:
            return query
        if current_user_org_type == "school":
            return query.join(SchoolModel, SchoolModel.id == BusModel.school_id).where(
                SchoolModel.organization_id == current_user_org_id
            )
        return query.where(BusModel.organization_id == current_user_org_id)

    async def _get_organization(self, organization_id: str) -> OrganizationModel:
        org = await self.db.get(OrganizationModel, organization_id)
        if not org:
            raise HTTPException(status_code=400, detail="Organization not found")
        return org

    async def _ensure_company_school_contract(self, company_org_id: str, school_org_id: Optional[str]) -> None:
        if not school_org_id:
            raise HTTPException(status_code=400, detail="School has no organization")
        if school_org_id == company_org_id:
            return
        stmt = select(ContractModel.id).where(
            ContractModel.company_org_id == company_org_id,
            ContractModel.school_org_id == school_org_id,
            ContractModel.is_active == True,
        )
        if (await self.db.execute(stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                status_code=400,
                detail="No active contract between selected school and bus organization",
            )

    async def get_buses(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
        school_id: Optional[str] = None,
    ) -> Tuple[List[BusModel], int]:
        query = select(BusModel).options(
            selectinload(BusModel.current_driver),
            selectinload(BusModel.school),
        )
        count_query = select(func.count()).select_from(BusModel)

        query = self._apply_bus_scope(query, current_user_org_id, current_user_org_type)
        count_query = self._apply_bus_scope(count_query, current_user_org_id, current_user_org_type)

        if school_id:
            query = query.where(BusModel.school_id == school_id)
            count_query = count_query.where(BusModel.school_id == school_id)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_bus_by_id(
        self,
        bus_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> Optional[BusModel]:
        query = (
            select(BusModel)
            .options(selectinload(BusModel.current_driver), selectinload(BusModel.school))
            .where(BusModel.id == bus_id)
        )
        query = self._apply_bus_scope(query, current_user_org_id, current_user_org_type)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_bus(
        self,
        bus: BusCreate,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> BusModel:
        stmt = select(BusModel).where(BusModel.plate_number == bus.plate_number)
        if (await self.db.execute(stmt)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Plate number already exists")

        if current_user_org_id is not None and bus.organization_id and bus.organization_id != current_user_org_id:
            raise HTTPException(status_code=403, detail="Cannot override tenant organization")

        organization_id = current_user_org_id if current_user_org_id is not None else bus.organization_id
        if not organization_id:
            raise HTTPException(
                status_code=400,
                detail="organization_id is required for super_admin bus creation",
            )

        owner_org = await self._get_organization(organization_id)
        owner_org_type = owner_org.type.value

        school_query = select(SchoolModel).where(SchoolModel.id == bus.school_id)
        if current_user_org_id and current_user_org_type == "school":
            school_query = school_query.where(SchoolModel.organization_id == current_user_org_id)
        school = (await self.db.execute(school_query)).scalar_one_or_none()
        if not school:
            raise HTTPException(status_code=400, detail="School not found or access denied")

        if owner_org_type == "transport_company":
            await self._ensure_company_school_contract(organization_id, school.organization_id)

        if bus.current_driver_id:
            driver_query = select(UserModel).where(
                UserModel.id == bus.current_driver_id,
                UserModel.organization_id == organization_id,
            )
            driver = (await self.db.execute(driver_query)).scalar_one_or_none()
            if not driver:
                raise HTTPException(status_code=400, detail="Driver not found or access denied")
            if driver.role.value != "sofor":
                raise HTTPException(status_code=400, detail="User is not a driver (sofor)")

        new_bus = BusModel(
            id=str(uuid4()),
            plate_number=bus.plate_number,
            capacity=bus.capacity,
            school_id=bus.school_id,
            organization_id=organization_id,
            current_driver_id=bus.current_driver_id,
        )
        self.db.add(new_bus)
        await self.db.commit()
        return await self.get_bus_by_id(new_bus.id)

    async def update_bus(
        self,
        bus_id: str,
        bus_update: BusUpdate,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> BusModel:
        query = select(BusModel).where(BusModel.id == bus_id)
        query = self._apply_bus_scope(query, current_user_org_id, current_user_org_type)
        db_bus = (await self.db.execute(query)).scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")

        if bus_update.plate_number and bus_update.plate_number != db_bus.plate_number:
            stmt = select(BusModel).where(BusModel.plate_number == bus_update.plate_number)
            if (await self.db.execute(stmt)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Plate number already exists")

        if current_user_org_id is not None and bus_update.organization_id and bus_update.organization_id != current_user_org_id:
            raise HTTPException(status_code=403, detail="Cannot override tenant organization")

        new_organization_id = db_bus.organization_id
        if bus_update.organization_id is not None:
            new_organization_id = bus_update.organization_id
        if not new_organization_id:
            raise HTTPException(status_code=400, detail="Bus organization cannot be empty")

        owner_org = await self._get_organization(new_organization_id)
        owner_org_type = owner_org.type.value

        target_school_id = bus_update.school_id or db_bus.school_id
        school_query = select(SchoolModel).where(SchoolModel.id == target_school_id)
        if current_user_org_id and current_user_org_type == "school":
            school_query = school_query.where(SchoolModel.organization_id == current_user_org_id)
        school = (await self.db.execute(school_query)).scalar_one_or_none()
        if not school:
            raise HTTPException(status_code=400, detail="School not found or access denied")

        if owner_org_type == "transport_company":
            await self._ensure_company_school_contract(new_organization_id, school.organization_id)

        if bus_update.current_driver_id:
            driver_query = select(UserModel).where(
                UserModel.id == bus_update.current_driver_id,
                UserModel.organization_id == new_organization_id,
            )
            driver = (await self.db.execute(driver_query)).scalar_one_or_none()
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
        if bus_update.organization_id is not None:
            db_bus.organization_id = bus_update.organization_id

        await self.db.commit()

        reloaded = await self.get_bus_by_id(
            bus_id,
            current_user_org_id=current_user_org_id,
            current_user_org_type=current_user_org_type,
        )
        if not reloaded:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")
        return reloaded

    async def delete_bus(
        self,
        bus_id: str,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ):
        query = select(BusModel).where(BusModel.id == bus_id)
        query = self._apply_bus_scope(query, current_user_org_id, current_user_org_type)
        db_bus = (await self.db.execute(query)).scalar_one_or_none()
        if not db_bus:
            raise HTTPException(status_code=404, detail="Bus not found or access denied")

        stmt = select(func.count()).select_from(AttendanceLog).where(AttendanceLog.bus_id == bus_id)
        log_count = (await self.db.execute(stmt)).scalar()
        if log_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete bus: {log_count} attendance log(s) reference it. Archive instead.",
            )

        await self.db.delete(db_bus)
        await self.db.commit()

    async def get_bus_locations(
        self,
        current_user_org_id: Optional[str] = None,
        current_user_org_type: Optional[str] = None,
    ) -> List[BusLocation]:
        query = select(BusLocation).join(BusModel, BusModel.id == BusLocation.bus_id)
        if current_user_org_id:
            if current_user_org_type == "school":
                query = query.join(SchoolModel, SchoolModel.id == BusModel.school_id).where(
                    SchoolModel.organization_id == current_user_org_id
                )
            else:
                query = query.where(BusModel.organization_id == current_user_org_id)
        query = query.distinct(BusLocation.bus_id).order_by(BusLocation.bus_id, BusLocation.timestamp.desc())
        result = await self.db.execute(query)
        return result.scalars().all()
