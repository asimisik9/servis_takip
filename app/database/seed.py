from sqlalchemy import select
from .models.user import User, UserRole
from .database import AsyncSessionLocal
from ..core.security import hash_password
from ..core.config import settings
from uuid import uuid4
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

async def create_admin_if_not_exists():
    """Admin kullanıcısı yoksa oluşturur"""
    async with AsyncSessionLocal() as db:
        try:
            # Check if admin exists
            query = select(User).where(User.email == settings.FIRST_SUPERUSER)
            result = await db.execute(query)
            admin = result.scalar_one_or_none()
            
            if not admin:
                # Create admin user
                admin = User(
                    id=str(uuid4()),
                    full_name="System Administrator",
                    email=settings.FIRST_SUPERUSER,
                    phone_number="+905550000000",
                    password_hash=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                    role=UserRole.admin,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(admin)
                await db.commit()
                logger.info(f"Admin user created successfully: {settings.FIRST_SUPERUSER}")
            else:
                logger.info("Admin user already exists.")
        except Exception as e:
            logger.error(f"Error seeding admin user: {e}")
