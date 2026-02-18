from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import status, WebSocket
from jose import jwt, JWTError
from datetime import datetime, timezone

from ..database import models
from ..core.security import SECRET_KEY, ALGORITHM, is_token_stale_for_password_change
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
            except Exception:
                is_blacklisted = None
            if is_blacklisted:
                return None

            # Secondary check in DB for Redis misses/restarts.
            try:
                from ..database.models.token_blacklist import TokenBlacklist

                stmt = select(TokenBlacklist).where(
                    TokenBlacklist.token == token,
                    TokenBlacklist.expires_at > datetime.now(timezone.utc)
                )
                result = await self.db.execute(stmt)
                if result.scalar_one_or_none():
                    try:
                        await redis_manager.set(f"blacklist:{token}", "1", ex=3600)
                    except Exception:
                        pass
                    return None
            except Exception:
                # Fail-closed if revocation state cannot be validated.
                return None
            
            query = select(models.User).where(models.User.email == email)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if user and is_token_stale_for_password_change(payload, user.password_changed_at):
                return None

            if user and not user.is_email_verified:
                return None
            
            # Check is_active if field exists
            if user and hasattr(user, 'is_active') and not user.is_active:
                return None
            
            return user
        except JWTError:
            return None

    async def validate_ws_access(self, user: models.User, bus_id: str) -> bool:
        if user.role.value == "super_admin":
            return True

        if user.role.value == "admin":
            if not user.organization_id:
                return False

            # Admin can only monitor buses within their own organization scope.
            stmt = select(models.Bus).where(
                models.Bus.id == bus_id,
                models.Bus.organization_id == user.organization_id,
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none() is not None
        
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
