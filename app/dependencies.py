from typing import Annotated, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from .database.database import AsyncSessionLocal
from .database.models.user import User as UserModel, UserRole
from .database.schemas.user import User
from .core.security import SECRET_KEY, ALGORITHM
from .core.config import settings
from .core.redis import redis_manager
from .services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Database dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db)
):
    """
    JWT token'dan kullanıcı bilgilerini çıkarır.
    Token blacklist kontrolü Redis üzerinden yapılır.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if token is blacklisted (Redis — O(1) lookup)
    is_blacklisted = await redis_manager.get(f"blacklist:{token}")
    if is_blacklisted:
        raise credentials_exception
    
    # Fallback: Check DB blacklist if Redis missed (e.g. after Redis restart)
    if not is_blacklisted:
        try:
            from .database.models.token_blacklist import TokenBlacklist
            from datetime import datetime, timezone
            stmt = select(TokenBlacklist).where(
                TokenBlacklist.token == token,
                TokenBlacklist.expires_at > datetime.now(timezone.utc)
            )
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                # Re-populate Redis so subsequent checks are fast
                try:
                    await redis_manager.set(f"blacklist:{token}", "1", ex=3600)
                except Exception:
                    pass
                raise credentials_exception
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"DB blacklist check failed: {e}")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None:
            raise credentials_exception
        # Ensure this is an access token, not a refresh token
        if token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    from sqlalchemy.orm import selectinload
    query = select(UserModel).options(selectinload(UserModel.organization)).where(UserModel.email == email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise credentials_exception
    
    # Check if user account is deactivated
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
    
    return User.model_validate(user)

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)):
        if user.role.value not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user

# Role dependencies
# super_admin veya admin (organizasyon admin'i) - admin paneli erişimi
get_current_admin_user = RoleChecker(["admin", "super_admin"])
# Sadece super_admin - platform seviyesi işlemler (organizasyon yönetimi)
get_current_super_admin = RoleChecker(["super_admin"])
# Driver ve parent - mobil uygulama kullanıcıları
get_current_driver_user = RoleChecker(["sofor"])
get_current_parent_user = RoleChecker(["veli"])

