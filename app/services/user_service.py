from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import uuid4
from typing import List, Optional, Tuple

from ..database.models.user import User as UserModel, UserRole
from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel
from ..database.schemas.user import UserCreate, UserUpdate
from ..core.security import hash_password

import logging
logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(
        self, 
        skip: int = 0, 
        limit: int = 100,
        current_user_org_id: Optional[str] = None
    ) -> Tuple[List[UserModel], int]:
        """
        Get users with tenant filtering and total count.
        current_user_org_id: None = super-admin (sees all), value = tenant admin (filtered)
        Returns: (users, total_count)
        """
        query = select(UserModel).options(selectinload(UserModel.organization))
        count_query = select(func.count()).select_from(UserModel)
        
        # Tenant filter
        if current_user_org_id is not None:
            query = query.where(UserModel.organization_id == current_user_org_id)
            count_query = count_query.where(UserModel.organization_id == current_user_org_id)
        
        # Get total count
        total = (await self.db.execute(count_query)).scalar() or 0
        
        # Get paginated results
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        query = select(UserModel).options(selectinload(UserModel.organization)).where(UserModel.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user: UserCreate, current_user_org_id: Optional[str] = None) -> UserModel:
        # Check email
        query = select(UserModel).where(UserModel.email == user.email)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
            
        # Check phone
        query = select(UserModel).where(UserModel.phone_number == user.phone_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")

        # Determine organization_id
        # If created by tenant admin -> forced to their org
        # If created by super admin -> can specify org_id in request
        org_id = current_user_org_id if current_user_org_id else user.organization_id

        # Tenant admins cannot create super_admin accounts.
        if current_user_org_id is not None and user.role.value == UserRole.super_admin.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admins cannot create super_admin users"
            )
        if user.role == UserRole.admin and org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin users must belong to an organization"
            )

        new_user = UserModel(
            id=str(uuid4()),
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            password_hash=hash_password(user.password),
            role=user.role,
            organization_id=org_id
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def update_user(self, user_id: str, user_update: UserUpdate, current_user_org_id: Optional[str] = None) -> UserModel:
        query = select(UserModel).where(UserModel.id == user_id)
        if current_user_org_id:
            query = query.where(UserModel.organization_id == current_user_org_id)
            
        db_user = (await self.db.execute(query)).scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found or access denied")

        if user_update.email and user_update.email != db_user.email:
            query = select(UserModel).where(UserModel.email == user_update.email)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Email already registered")

        if user_update.phone_number and user_update.phone_number != db_user.phone_number:
            query = select(UserModel).where(UserModel.phone_number == user_update.phone_number)
            if (await self.db.execute(query)).scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Phone number already registered")

        if user_update.full_name is not None:
            db_user.full_name = user_update.full_name
        if user_update.email is not None:
            db_user.email = user_update.email
        if user_update.phone_number is not None:
            db_user.phone_number = user_update.phone_number
        if user_update.role is not None:
            # Tenant admins cannot promote users to super_admin.
            if current_user_org_id is not None and user_update.role.value == UserRole.super_admin.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant admins cannot assign super_admin role"
                )
            if db_user.role != user_update.role:
                logger.warning(f"Role change: user={user_id} from={db_user.role.value} to={user_update.role}")
            db_user.role = user_update.role
        
        # Only Super Admin (current_user_org_id is None) can change organization info
        if user_update.organization_id is not None and current_user_org_id is None:
            db_user.organization_id = user_update.organization_id

        # Defense-in-depth: admin role must always stay tenant-scoped.
        if db_user.role == UserRole.admin and db_user.organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin users must belong to an organization"
            )
            
        if user_update.password is not None:
            db_user.password_hash = hash_password(user_update.password)

        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def delete_user(self, user_id: str, current_user_id: str, current_user_org_id: Optional[str] = None):
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="Admin cannot delete themselves")
            
        query = select(UserModel).where(UserModel.id == user_id)
        if current_user_org_id:
            query = query.where(UserModel.organization_id == current_user_org_id)
            
        db_user = (await self.db.execute(query)).scalar_one_or_none()
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found or access denied")

        # Check if user is a contact person for any school (RESTRICT)
        query = select(func.count()).select_from(SchoolModel).where(SchoolModel.contact_person_id == user_id)
        school_count = (await self.db.execute(query)).scalar()
        if school_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete user: still contact person for {school_count} school(s). Reassign first."
            )

        # Check if user is a driver for any bus (SET NULL handled by FK, but warn)
        query = select(func.count()).select_from(BusModel).where(BusModel.current_driver_id == user_id)
        bus_count = (await self.db.execute(query)).scalar()

        # Soft-delete: deactivate instead of hard delete
        db_user.is_active = False
        await self.db.commit()
        await self.db.refresh(db_user)
        return {"detail": f"User deactivated. {bus_count} bus(es) will have driver unlinked." if bus_count else "User deactivated."}
