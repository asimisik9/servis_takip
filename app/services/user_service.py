from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from uuid import uuid4
from typing import List, Optional

from ..database.models.user import User as UserModel
from ..database.schemas.user import UserCreate, UserUpdate
from ..core.security import hash_password

class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[UserModel]:
        query = select(UserModel).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_user_by_id(self, user_id: str) -> Optional[UserModel]:
        query = select(UserModel).where(UserModel.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user: UserCreate) -> UserModel:
        # Check email
        query = select(UserModel).where(UserModel.email == user.email)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
            
        # Check phone
        query = select(UserModel).where(UserModel.phone_number == user.phone_number)
        if (await self.db.execute(query)).scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")

        new_user = UserModel(
            id=str(uuid4()),
            full_name=user.full_name,
            email=user.email,
            phone_number=user.phone_number,
            password_hash=hash_password(user.password),
            role=user.role
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def update_user(self, user_id: str, user_update: UserUpdate) -> UserModel:
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

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
            db_user.role = user_update.role
        if user_update.password is not None:
            db_user.password_hash = hash_password(user_update.password)

        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def delete_user(self, user_id: str, current_user_id: str):
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="Admin cannot delete themselves")
            
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
            
        await self.db.delete(db_user)
        await self.db.commit()
