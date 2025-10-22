from sqlalchemy import select
from .models.user import User, UserRole
from .database import AsyncSessionLocal
from argon2 import PasswordHasher
from uuid import uuid4
from datetime import datetime

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hash a password using argon2"""
    return ph.hash(password)

async def create_admin_if_not_exists():
    """Admin kullanıcısı yoksa oluşturur"""
    async with AsyncSessionLocal() as db:
        # Check if admin exists
        query = select(User).where(User.role == UserRole.admin)
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        
        if not admin:
            # Create admin user
            admin = User(
                id=str(uuid4()),
                full_name="Admin User",
                email="admin@example.com",
                phone_number="+905551234567",
                password_hash=hash_password("admin123"),
                role=UserRole.admin,
                created_at=datetime.utcnow()
            )
            db.add(admin)
            await db.commit()
            print("Admin user created successfully!")
        else:
            print("Admin user already exists.")