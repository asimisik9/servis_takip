from fastapi import APIRouter, Depends, status
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User
from ...database.schemas.school import School, SchoolCreate, SchoolUpdate
from ...dependencies import get_db, get_current_admin_user
from ...services.school_service import SchoolService

router = APIRouter(tags=["admin-schools"])

@router.get("/schools", response_model=List[School])
async def list_schools(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    service = SchoolService(db)
    return await service.get_schools(skip, limit)

@router.post("/schools", response_model=School, status_code=status.HTTP_201_CREATED)
async def create_school(
    school: SchoolCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    return await service.create_school(school)

@router.get("/schools/{school_id}", response_model=School)
async def get_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    return await service.get_school_by_id(unquote(school_id))

@router.put("/schools/{school_id}", response_model=School)
async def update_school(
    school_id: str,
    school: SchoolUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    return await service.update_school(unquote(school_id), school)

@router.delete("/schools/{school_id}", status_code=status.HTTP_200_OK)
async def delete_school(
    school_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = SchoolService(db)
    await service.delete_school(unquote(school_id))
    return {"detail": "School deleted successfully"}
