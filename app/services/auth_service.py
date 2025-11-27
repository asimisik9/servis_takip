from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from datetime import datetime, timezone
from uuid import uuid4
from jose import jwt, JWTError

from ..database.models.user import User as UserModel
from ..database.models.token_blacklist import TokenBlacklist
from ..database.schemas.user import UserCreate
from ..core.security import (
    hash_password, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    SECRET_KEY, 
    ALGORITHM
)

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserCreate) -> UserModel:
        # Check email
        query = select(UserModel).where(UserModel.email == user_data.email)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Check phone
        query = select(UserModel).where(UserModel.phone_number == user_data.phone_number)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Phone number already registered")
        
        hashed_password = hash_password(user_data.password)
        new_user = UserModel(
            id=str(uuid4()),
            full_name=user_data.full_name,
            email=user_data.email,
            phone_number=user_data.phone_number,
            password_hash=hashed_password,
            role=user_data.role,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def authenticate_user(self, email: str, password: str):
        query = select(UserModel).where(UserModel.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
            
        return user

    async def create_tokens(self, user: UserModel):
        token_data = {
            "sub": user.email,
            "id": user.id,
            "role": user.role.value
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        return access_token, refresh_token

    async def logout(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp = payload.get("exp")
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            
            blacklist_token = TokenBlacklist(token=token, expires_at=expires_at)
            self.db.add(blacklist_token)
            await self.db.commit()
        except Exception:
            pass # Fail silently

    async def refresh_token(self, refresh_token: str):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Check blacklist
        query = select(TokenBlacklist).where(TokenBlacklist.token == refresh_token)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise credentials_exception
            
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
            
        query = select(UserModel).where(UserModel.email == email)
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise credentials_exception
            
        # Blacklist old token
        await self.logout(refresh_token)
        
        return await self.create_tokens(user), user
