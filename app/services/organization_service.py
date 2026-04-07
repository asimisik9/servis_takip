# app/services/organization_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
from uuid import uuid4
from typing import List, Optional
from datetime import date, datetime, timezone
import logging

from ..database.models.organization import Organization as OrganizationModel, OrganizationType
from ..database.models.school_company_contract import SchoolCompanyContract as ContractModel
from ..database.models.user import User as UserModel, UserRole
from ..database.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationAdminCreate,
    SchoolCompanyContractCreate,
    SchoolCompanyContractUpdate,
)
from ..core.security import hash_password

logger = logging.getLogger(__name__)


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ===== Organization CRUD =====

    async def _create_organization_admin(
        self,
        organization_id: str,
        admin_data: OrganizationAdminCreate,
    ) -> UserModel:
        email_exists = (await self.db.execute(
            select(UserModel.id).where(UserModel.email == admin_data.email)
        )).scalar_one_or_none()
        if email_exists:
            raise HTTPException(status_code=400, detail="Admin email already registered")

        phone_exists = (await self.db.execute(
            select(UserModel.id).where(UserModel.phone_number == admin_data.phone_number)
        )).scalar_one_or_none()
        if phone_exists:
            raise HTTPException(status_code=400, detail="Admin phone number already registered")

        admin_user = UserModel(
            id=str(uuid4()),
            full_name=admin_data.full_name,
            email=admin_data.email,
            phone_number=admin_data.phone_number,
            password_hash=hash_password(admin_data.password),
            role=UserRole.admin,
            organization_id=organization_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(admin_user)
        return admin_user

    async def create_organization(self, data: OrganizationCreate) -> OrganizationModel:
        """Yeni organization oluştur (okul veya servis şirketi)"""
        org = OrganizationModel(
            id=str(uuid4()),
            name=data.name,
            type=OrganizationType(data.type.value)
        )
        self.db.add(org)

        if data.admin is not None:
            await self._create_organization_admin(org.id, data.admin)

        await self.db.commit()
        await self.db.refresh(org)
        if data.admin is not None:
            logger.info(f"Created organization with admin: {org.name} (type={org.type.value})")
        else:
            logger.info(f"Created organization: {org.name} (type={org.type.value})")
        return org

    async def get_organization(self, org_id: str) -> OrganizationModel:
        """Organization detayını getir"""
        query = select(OrganizationModel).where(OrganizationModel.id == org_id)
        result = await self.db.execute(query)
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org

    async def get_organizations(
        self, 
        org_type: Optional[OrganizationType] = None,
        skip: int = 0, 
        limit: int = 100
    ):
        """Tüm organizasyonları listele (items, total) tuple döner"""
        base_query = select(OrganizationModel)
        if org_type:
            base_query = base_query.where(OrganizationModel.type == org_type)
        
        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Fetch items
        query = base_query.order_by(OrganizationModel.name).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update_organization(self, org_id: str, data: OrganizationUpdate) -> OrganizationModel:
        """Organization güncelle"""
        org = await self.get_organization(org_id)
        if data.name is not None:
            org.name = data.name
        if data.is_active is not None:
            org.is_active = data.is_active
        await self.db.commit()
        await self.db.refresh(org)
        return org

    async def delete_organization(self, org_id: str) -> None:
        """Organization sil (soft delete - is_active=False)"""
        org = await self.get_organization(org_id)
        org.is_active = False
        await self.db.commit()
        logger.info(f"Soft deleted organization: {org.name}")

    # ===== Contract CRUD =====
    
    async def create_contract(self, data: SchoolCompanyContractCreate) -> ContractModel:
        """Okul-Servis şirketi sözleşmesi oluştur"""
        # Validate school org
        school_org = await self.get_organization(data.school_org_id)
        if school_org.type != OrganizationType.school:
            raise HTTPException(
                status_code=400, 
                detail="school_org_id must reference a school organization"
            )
        
        # Validate company org
        company_org = await self.get_organization(data.company_org_id)
        if company_org.type != OrganizationType.transport_company:
            raise HTTPException(
                status_code=400,
                detail="company_org_id must reference a transport_company organization"
            )
        
        # Check for existing contract
        existing = await self._get_contract_by_orgs(data.school_org_id, data.company_org_id)
        if existing:
            if existing.is_active:
                raise HTTPException(
                    status_code=409,
                    detail="Contract already exists between these organizations"
                )

            # Re-activate historical contract because DB enforces unique school/company pair.
            existing.is_active = True
            existing.start_date = data.start_date
            existing.end_date = data.end_date
            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"Re-activated contract: {school_org.name} <-> {company_org.name}")
            return existing
        
        contract = ContractModel(
            id=str(uuid4()),
            school_org_id=data.school_org_id,
            company_org_id=data.company_org_id,
            start_date=data.start_date,
            end_date=data.end_date
        )
        self.db.add(contract)
        await self.db.commit()
        await self.db.refresh(contract)
        logger.info(f"Created contract: {school_org.name} <-> {company_org.name}")
        return contract

    async def get_contract(self, contract_id: str) -> ContractModel:
        """Sözleşme detayını getir"""
        query = select(ContractModel).where(ContractModel.id == contract_id)
        result = await self.db.execute(query)
        contract = result.scalar_one_or_none()
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        return contract

    async def get_contracts(
        self,
        school_org_id: Optional[str] = None,
        company_org_id: Optional[str] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[ContractModel], int]:
        """Sözleşmeleri listele. (items, total) tuple döner."""
        from sqlalchemy import func
        base_conditions = []
        if school_org_id:
            base_conditions.append(ContractModel.school_org_id == school_org_id)
        if company_org_id:
            base_conditions.append(ContractModel.company_org_id == company_org_id)
        if active_only:
            base_conditions.append(ContractModel.is_active == True)

        count_query = select(func.count(ContractModel.id)).where(*base_conditions)
        total = (await self.db.execute(count_query)).scalar_one()

        query = (
            select(ContractModel)
            .options(
                selectinload(ContractModel.school_org),
                selectinload(ContractModel.company_org),
            )
            .where(*base_conditions)
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def terminate_contract(self, contract_id: str) -> ContractModel:
        """Sözleşmeyi sonlandır"""
        contract = await self.get_contract(contract_id)
        contract.is_active = False
        contract.end_date = date.today()
        await self.db.commit()
        await self.db.refresh(contract)
        logger.info(f"Terminated contract: {contract_id}")
        return contract

    # ===== Helper Methods =====
    
    async def _get_contract_by_orgs(
        self, 
        school_org_id: str, 
        company_org_id: str
    ) -> Optional[ContractModel]:
        """Belirli okul-şirket ikilisi için sözleşme getir"""
        query = select(ContractModel).where(
            ContractModel.school_org_id == school_org_id,
            ContractModel.company_org_id == company_org_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_schools_for_company(self, company_org_id: str) -> List[OrganizationModel]:
        """Bir servis şirketinin sözleşmeli okullarını getir"""
        query = (
            select(OrganizationModel)
            .join(ContractModel, ContractModel.school_org_id == OrganizationModel.id)
            .where(
                ContractModel.company_org_id == company_org_id,
                ContractModel.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_companies_for_school(self, school_org_id: str) -> List[OrganizationModel]:
        """Bir okulun sözleşmeli servis şirketlerini getir"""
        query = (
            select(OrganizationModel)
            .join(ContractModel, ContractModel.company_org_id == OrganizationModel.id)
            .where(
                ContractModel.school_org_id == school_org_id,
                ContractModel.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()
