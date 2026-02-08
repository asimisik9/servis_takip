# app/routers/admin/organizations.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date

from ...dependencies import get_db, get_current_admin_user, get_current_super_admin
from ...database.schemas.user import User
from ...database.models.user import UserRole
from ...database.schemas.organization import (
    OrganizationType,
    Organization,
    OrganizationCreate,
    OrganizationUpdate,
    SchoolCompanyContract,
    SchoolCompanyContractCreate,
)
from ...database.schemas.common import PaginatedResponse
from ...services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def get_organization_service(db: AsyncSession = Depends(get_db)) -> OrganizationService:
    return OrganizationService(db)


# ===== Organization Endpoints =====

@router.post("", response_model=Organization)
async def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_super_admin),
    service: OrganizationService = Depends(get_organization_service)
):
    """
    Yeni organization oluştur (okul veya servis şirketi).
    Sadece super_admin kullanabilir.
    """
    return await service.create_organization(data)


@router.get("", response_model=PaginatedResponse[Organization])
async def list_organizations(
    org_type: Optional[OrganizationType] = Query(None, description="Filter by type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_admin_user),
    service: OrganizationService = Depends(get_organization_service)
):
    """
    Organizasyonları listele.
    Super-admin tümünü görür, tenant-admin sadece kendisini görür.
    """
    # Tenant admin can only see their own organization
    if current_user.organization_id is not None:
        org = await service.get_organization(current_user.organization_id)
        return PaginatedResponse(items=[org], total=1, skip=0, limit=limit)
    organizations, total = await service.get_organizations(org_type=org_type, skip=skip, limit=limit)
    return PaginatedResponse(items=organizations, total=total, skip=skip, limit=limit)


@router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_admin_user),
    service: OrganizationService = Depends(get_organization_service)
):
    """Organization detayını getir."""
    org = await service.get_organization(org_id)
    
    # Tenant admin can only view their own organization
    if current_user.organization_id is not None and current_user.organization_id != org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    
    return org


@router.put("/{org_id}", response_model=Organization)
async def update_organization(
    org_id: str,
    data: OrganizationUpdate,
    current_user: User = Depends(get_current_admin_user),
    service: OrganizationService = Depends(get_organization_service)
):
    """Organization güncelle."""
    # Tenant admin can only update their own organization
    if current_user.organization_id is not None and current_user.organization_id != org_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Access denied")
    
    return await service.update_organization(org_id, data)


@router.delete("/{org_id}")
async def delete_organization(
    org_id: str,
    current_user: User = Depends(get_current_super_admin),
    service: OrganizationService = Depends(get_organization_service)
):
    """Organization sil (soft delete). Sadece super_admin."""
    await service.delete_organization(org_id)
    return {"message": "Organization deleted successfully"}


# ===== Contract Endpoints =====

@router.post("/contracts", response_model=SchoolCompanyContract)
async def create_contract(
    data: SchoolCompanyContractCreate,
    current_user: User = Depends(get_current_super_admin),
    service: OrganizationService = Depends(get_organization_service)
):
    """
    Okul-Servis şirketi sözleşmesi oluştur.
    Sadece super_admin kullanabilir.
    """
    return await service.create_contract(data)


@router.get("/contracts", response_model=List[SchoolCompanyContract])
async def list_contracts(
    school_org_id: Optional[str] = Query(None),
    company_org_id: Optional[str] = Query(None),
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_admin_user),
    service: OrganizationService = Depends(get_organization_service)
):
    """
    Sözleşmeleri listele.
    Tenant-admin sadece kendi organizasyonuyla ilgili sözleşmeleri görür.
    """
    # If tenant admin, filter by their organization
    if current_user.organization_id is not None:
        # Determine if user's org is school or company
        user_org = await service.get_organization(current_user.organization_id)
        from ...database.models.organization import OrganizationType as OrgTypeModel
        if user_org.type == OrgTypeModel.school:
            school_org_id = current_user.organization_id
        else:
            company_org_id = current_user.organization_id
    
    return await service.get_contracts(
        school_org_id=school_org_id,
        company_org_id=company_org_id,
        active_only=active_only,
        skip=skip,
        limit=limit
    )


@router.delete("/contracts/{contract_id}")
async def terminate_contract(
    contract_id: str,
    current_user: User = Depends(get_current_super_admin),
    service: OrganizationService = Depends(get_organization_service)
):
    """Sözleşmeyi sonlandır. Sadece super_admin."""
    await service.terminate_contract(contract_id)
    return {"message": "Contract terminated successfully"}

