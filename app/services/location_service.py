from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status, WebSocket
from jose import jwt, JWTError

from ..database import models
from ..core.security import SECRET_KEY, ALGORITHM

class LocationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_from_token(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            
            query = select(models.User).where(models.User.email == email)
            result = await self.db.execute(query)
            return result.scalar_one_or_none()
        except JWTError:
            return None

    async def validate_ws_access(self, user: models.User, bus_id: str) -> bool:
        if user.role.value == "veli":
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
