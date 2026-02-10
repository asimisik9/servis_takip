from sqlalchemy import select
from .models.user import User, UserRole
from .database import AsyncSessionLocal
from ..core.security import hash_password, verify_password
from ..core.config import settings
from uuid import uuid4
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

async def create_admin_if_not_exists():
    """Initial super admin yoksa oluşturur, varsa rolünü doğrular."""
    async with AsyncSessionLocal() as db:
        try:
            # Check if initial super admin exists
            query = select(User).where(User.email == settings.FIRST_SUPERUSER)
            result = await db.execute(query)
            admin = result.scalar_one_or_none()
            
            if not admin:
                # Create initial super admin user
                admin = User(
                    id=str(uuid4()),
                    full_name="System Administrator",
                    email=settings.FIRST_SUPERUSER,
                    phone_number="+905550000000",
                    password_hash=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                    role=UserRole.super_admin,
                    created_at=datetime.now(timezone.utc)
                )
                db.add(admin)
                await db.commit()
                logger.info("Initial super admin created successfully.")
            else:
                if admin.role != UserRole.super_admin:
                    # Guardrail: do not auto-elevate arbitrary account with matching email.
                    # Only repair legacy seed user if configured bootstrap password still matches.
                    if verify_password(settings.FIRST_SUPERUSER_PASSWORD, admin.password_hash):
                        admin.role = UserRole.super_admin
                        await db.commit()
                        logger.warning("Initial user role upgraded to super_admin after credential verification.")
                    else:
                        logger.critical(
                            "FIRST_SUPERUSER exists but is not super_admin and credentials do not match bootstrap config. "
                            "Automatic role upgrade refused."
                        )
                else:
                    logger.info("Initial super admin already exists.")
        except Exception as e:
            logger.error(f"Error seeding admin user: {e}")
