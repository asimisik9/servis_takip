from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import List, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import unquote

from ...database.schemas.user import User, UserCreate, UserUpdate
from ...database.schemas.common import PaginatedResponse
from ...dependencies import get_db, get_current_admin_user
from ...services.user_service import UserService

router = APIRouter(tags=["admin-users"])

@router.get("/users", response_model=PaginatedResponse[User])
async def list_users(
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
):
    """List users with tenant filtering and pagination."""
    service = UserService(db)
    users, total = await service.get_users(
        skip=skip, 
        limit=limit, 
        current_user_org_id=current_user.organization_id
    )
    return PaginatedResponse(items=users, total=total, skip=skip, limit=limit)

@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    return await service.create_user(user)

@router.get("/users/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    user = await service.get_user_by_id(unquote(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user: UserUpdate,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    return await service.update_user(unquote(user_id), user)

@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: str,
    current_user: Annotated[User, Depends(get_current_admin_user)],
    db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    await service.delete_user(unquote(user_id), current_user.id)
    return {"detail": "User deleted successfully"}
