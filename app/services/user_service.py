from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from uuid import uuid4
from typing import List, Optional, Tuple

from ..database.models.user import User as UserModel, UserRole
from ..database.models.organization import Organization as OrganizationModel
from ..database.models.bus import Bus as BusModel
from ..database.models.school import School as SchoolModel
from ..database.schemas.user import UserCreate, UserUpdate
from ..core.security import hash_password

import logging
logger = logging.getLogger(__name__)


TENANT_BOUND_ROLES = {UserRole.admin, UserRole.sofor, UserRole.veli}


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _coerce_role(role: UserRole | str) -> UserRole:
        if isinstance(role, UserRole):
            return role
        raw_value = role.value if hasattr(role, "value") else role
        return UserRole(raw_value)

    async def _ensure_organization_exists(self, organization_id: Optional[str]) -> None:
        if organization_id is None:
            return
        organization = await self.db.get(OrganizationModel, organization_id)
        if not organization:
            raise HTTPException(status_code=400, detail="Organization not found")

    @classmethod
    def _validate_role_organization_matrix(cls, role: UserRole | str, organization_id: Optional[str]) -> None:
        role = cls._coerce_role(role)
        if role == UserRole.super_admin:
            if organization_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="super_admin users cannot be bound to an organization",
                )
            return

        if role in TENANT_BOUND_ROLES and organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{role.value} users must belong to an organization",
            )

    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user_org_id: Optional[str] = None,
        organization_filter: Optional[str] = None,
    ) -> Tuple[List[UserModel], int]:
        """
        Get users with tenant filtering and total count.
        current_user_org_id: None = super-admin (sees all), value = tenant admin (filtered)
        organization_filter: optional super-admin filter by organization_id
        Returns: (users, total_count)
        """
        query = select(UserModel).options(selectinload(UserModel.organization))
        count_query = select(func.count()).select_from(UserModel)

        # Tenant filter (always dominant for tenant admins)
        if current_user_org_id is not None:
            query = query.where(UserModel.organization_id == current_user_org_id)
            count_query = count_query.where(UserModel.organization_id == current_user_org_id)
        elif organization_filter is not None:
            query = query.where(UserModel.organization_id == organization_filter)
            count_query = count_query.where(UserModel.organization_id == organization_filter)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_user_by_id(self, user_id: str, org_id: Optional[str] = None) -> Optional[UserModel]:
        query = select(UserModel).options(selectinload(UserModel.organization)).where(UserModel.id == user_id)
        if org_id:
            query = query.where(UserModel.organization_id == org_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user: UserCreate, current_user_org_id: Optional[str] = None) -> UserModel:
        query = select(UserModel).where(UserModel.email == user.email)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        query = select(UserModel).where(UserModel.phone_number == user.phone_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")

        is_tenant_admin = current_user_org_id is not None
        target_role = self._coerce_role(user.role)

        if is_tenant_admin and target_role == UserRole.super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admins cannot create super_admin users",
            )

        organization_id = current_user_org_id if is_tenant_admin else user.organization_id

        await self._ensure_organization_exists(organization_id)
        self._validate_role_organization_matrix(target_role, organization_id)

        new_user = UserModel(
            id=str(uuid4()),
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            password_hash=hash_password(user.password),
            role=target_role,
            organization_id=organization_id,
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        # Response model accesses organization fields; reload with relationship to avoid lazy-load errors.
        hydrated_user = await self.get_user_by_id(new_user.id)
        if hydrated_user is None:
            raise HTTPException(status_code=500, detail="Created user could not be reloaded")
        return hydrated_user

    async def update_user(
        self,
        user_id: str,
        user_update: UserUpdate,
        current_user_org_id: Optional[str] = None,
    ) -> UserModel:
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

        is_tenant_admin = current_user_org_id is not None

        target_role = self._coerce_role(user_update.role) if user_update.role is not None else db_user.role
        if is_tenant_admin and target_role == UserRole.super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant admins cannot assign super_admin role",
            )

        if is_tenant_admin:
            target_organization_id = current_user_org_id
        else:
            if "organization_id" in user_update.model_fields_set:
                target_organization_id = user_update.organization_id
            else:
                target_organization_id = db_user.organization_id

        await self._ensure_organization_exists(target_organization_id)
        self._validate_role_organization_matrix(target_role, target_organization_id)

        if user_update.full_name is not None:
            db_user.full_name = user_update.full_name
        if user_update.email is not None:
            db_user.email = user_update.email
        if user_update.phone_number is not None:
            db_user.phone_number = user_update.phone_number
        if user_update.password is not None:
            db_user.password_hash = hash_password(user_update.password)

        if user_update.role is not None:
            normalized_role = self._coerce_role(user_update.role)
            if db_user.role != normalized_role:
                logger.warning(f"Role change: user={user_id} from={db_user.role.value} to={normalized_role.value}")
            db_user.role = normalized_role

        if is_tenant_admin:
            db_user.organization_id = current_user_org_id
        elif "organization_id" in user_update.model_fields_set:
            db_user.organization_id = user_update.organization_id

        await self.db.commit()
        await self.db.refresh(db_user)
        # Response model accesses organization fields; reload with relationship to avoid lazy-load errors.
        hydrated_user = await self.get_user_by_id(db_user.id)
        if hydrated_user is None:
            raise HTTPException(status_code=500, detail="Updated user could not be reloaded")
        return hydrated_user

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
                detail=f"Cannot delete user: still contact person for {school_count} school(s). Reassign first.",
            )

        # Check if user is a driver for any bus (SET NULL handled by FK, but warn)
        query = select(func.count()).select_from(BusModel).where(BusModel.current_driver_id == user_id)
        bus_count = (await self.db.execute(query)).scalar()

        # Soft-delete: deactivate instead of hard delete
        db_user.is_active = False
        await self.db.commit()
        await self.db.refresh(db_user)
        return {
            "detail": (
                f"User deactivated. {bus_count} bus(es) will have driver unlinked."
                if bus_count
                else "User deactivated."
            )
        }
