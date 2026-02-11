from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.school import School, SchoolCreate, SchoolUpdate
from ...database.schemas.common import PaginatedResponse
from ...dependencies import get_db, get_current_admin_user
from ...services.school_service import SchoolService

router = APIRouter(tags=["admin-schools"])

@router.get("/schools", response_model=PaginatedResponse[School])
async def list_schools(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    organization_id: Annotated[str | None, Query()] = None,
):
    """List schools with tenant filtering and pagination."""
    service = SchoolService(db)
    org_filter = organization_id if current_user.role.value == "super_admin" else None
    schools, total = await service.get_schools(
        skip=skip, 
        limit=limit, 
        current_user_org_id=current_user.organization_id,
        organization_filter=org_filter,
    )
    return PaginatedResponse(items=schools, total=total, skip=skip, limit=limit)

@router.post("/schools", response_model=School, status_code=status.HTTP_201_CREATED)
async def create_school(
    school: SchoolCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    return await service.create_school(
        school,
        current_user_org_id=current_user.organization_id
    )

@router.get("/schools/{school_id}", response_model=School)
async def get_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    school = await service.get_school_by_id(
        unquote(school_id),
        current_user_org_id=current_user.organization_id
    )
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school

@router.put("/schools/{school_id}", response_model=School)
async def update_school(
    school_id: str,
    school: SchoolUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    return await service.update_school(
        unquote(school_id),
        school,
        current_user_org_id=current_user.organization_id
    )

@router.delete("/schools/{school_id}", status_code=status.HTTP_200_OK)
async def delete_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    await service.delete_school(
        unquote(school_id),
        current_user_org_id=current_user.organization_id
    )
    return {"detail": "School deleted successfully"}


@router.post("/schools/geocode-all", status_code=status.HTTP_200_OK)
async def geocode_all_schools(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    """Geocode all schools that don't have coordinates yet"""
    service = SchoolService(db)
    result = await service.geocode_existing_schools(
        current_user_org_id=current_user.organization_id
    )
    return {
        "detail": f"Geocoded {result['updated']} schools successfully",
        "updated": result["updated"],
        "failed": result["failed"],
        "total": result["total"]
    }
