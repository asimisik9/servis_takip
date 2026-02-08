from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status, WebSocket
from jose import jwt, JWTError

from ..database import models
from ..core.security import SECRET_KEY, ALGORITHM
from ..core.redis import redis_manager

class LocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_from_token(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            token_type: str = payload.get("type")
            if email is None:
                return None
            # Only access tokens can be used for WebSocket auth
            if token_type != "access":
                return None
            
            # Check Redis blacklist
            try:
                is_blacklisted = await redis_manager.get(f"blacklist:{token}")
                if is_blacklisted:
                    return None
            except Exception:
                pass  # If Redis is down, allow through (DB check is too heavy for WS)
            
            query = select(models.User).where(models.User.email == email)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            # Check is_active if field exists
            if user and hasattr(user, 'is_active') and not user.is_active:
                return None
            
            return user
        except JWTError:
            return None

    async def validate_ws_access(self, user: models.User, bus_id: str) -> bool:
        if user.role.value == "admin":
            # Admins can monitor any bus
            return True
        
        elif user.role.value == "veli":
            # Veli sadece kendi çocuğunun servisini izleyebilir
            stmt = select(models.StudentBusAssignment).join(
                models.ParentStudentRelation,
                models.ParentStudentRelation.student_id == models.StudentBusAssignment.student_id
            ).where(
                models.ParentStudentRelation.parent_id == user.id,
                models.StudentBusAssignment.bus_id == bus_id
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none() is not None
                
        elif user.role.value == "sofor":
            # Şoför sadece kendi servisine bağlanabilir
            stmt = select(models.Bus).where(
                models.Bus.id == bus_id,
                models.Bus.current_driver_id == user.id
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none() is not None
            
        return False

    async def get_driver_bus(self, driver_id: str) -> models.Bus | None:
        query = select(models.Bus).where(models.Bus.current_driver_id == driver_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
