from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from datetime import datetime, timezone
from jose import jwt, JWTError
import logging

from ..database.models.user import User as UserModel
from ..database.schemas.user import UserCreate
from ..core.security import (
    verify_password, 
    create_access_token, 
    create_refresh_token,
    SECRET_KEY,
    REFRESH_SECRET_KEY,
    ALGORITHM
)
from ..core.redis import redis_manager

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, user_data: UserCreate) -> UserModel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled. Contact your administrator.",
        )

    async def authenticate_user(self, email: str, password: str):
        query = (
            select(UserModel)
            .options(selectinload(UserModel.organization))
            .where(UserModel.email == email)
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if hasattr(user, 'is_active') and not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Contact an administrator."
            )
            
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

    async def _blacklist_token(self, token: str, exp_timestamp: int):
        """Add token to Redis blacklist with TTL matching token expiry.
        Also persists to DB as fallback if Redis restarts."""
        now = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp_timestamp - now, 0)
        
        # Primary: Redis (fast, auto-expires)
        redis_ok = False
        if ttl > 0:
            try:
                await redis_manager.set(f"blacklist:{token}", "1", ex=ttl)
                redis_ok = True
            except Exception as e:
                logger.error(f"Failed to blacklist token in Redis: {e}")
        
        # Secondary: DB persistence (survives Redis restart)
        db_ok = False
        try:
            from ..database.models.token_blacklist import TokenBlacklist
            from ..database.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as db:
                blacklisted = TokenBlacklist(
                    token=token,
                    expires_at=datetime.fromtimestamp(exp_timestamp, tz=timezone.utc),
                    created_at=datetime.now(timezone.utc)
                )
                db.add(blacklisted)
                await db.commit()
                db_ok = True
        except Exception as e:
            logger.error(f"Failed to persist blacklisted token to DB: {e}")
            if not redis_ok:
                logger.critical("Token blacklist failed in BOTH Redis and DB! Token remains valid.")

        if not redis_ok and not db_ok:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token revocation failed"
            )

    async def logout(self, token: str):
        try:
            # Try decoding as access token first, then refresh
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            except JWTError:
                payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            
            exp = payload.get("exp", 0)
            await self._blacklist_token(token, exp)
        except HTTPException:
            raise
        except JWTError:
            pass  # Token already expired or invalid — no need to blacklist
        except Exception as e:
            logger.error(f"Unexpected error during logout: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed. Please try again."
            )

    async def refresh_token(self, refresh_token: str):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Check blacklist in Redis
        try:
            is_blacklisted = await redis_manager.get(f"blacklist:{refresh_token}")
        except Exception as e:
            logger.warning(f"Refresh Redis blacklist check failed: {e}")
            is_blacklisted = None
        if is_blacklisted:
            raise credentials_exception

        # Fallback: Check DB blacklist if Redis missed (e.g. after Redis restart)
        try:
            from ..database.models.token_blacklist import TokenBlacklist
            stmt = select(TokenBlacklist).where(
                TokenBlacklist.token == refresh_token,
                TokenBlacklist.expires_at > datetime.now(timezone.utc)
            )
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                try:
                    await redis_manager.set(f"blacklist:{refresh_token}", "1", ex=3600)
                except Exception:
                    pass
                raise credentials_exception
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Refresh DB blacklist check failed: {e}")
            # Fail-closed: we cannot safely validate revocation state.
            raise credentials_exception
            
        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            token_type: str = payload.get("type")
            if email is None:
                raise credentials_exception
            # Ensure this is actually a refresh token
            if token_type != "refresh":
                raise credentials_exception
        except JWTError:
            raise credentials_exception
            
        query = (
            select(UserModel)
            .options(selectinload(UserModel.organization))
            .where(UserModel.email == email)
        )
        result = await self.db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise credentials_exception
            
        # Blacklist old refresh token
        await self.logout(refresh_token)
        
        return await self.create_tokens(user), user
