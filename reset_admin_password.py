"""Admin kullanıcısının şifresini argon2 ile günceller"""
import asyncio
from sqlalchemy import select, update
from app.database.models.user import User, UserRole
from app.database.database import AsyncSessionLocal
from argon2 import PasswordHasher

ph = PasswordHasher()

async def reset_admin_password():
    async with AsyncSessionLocal() as db:
        # Admin kullanıcısını bul
        query = select(User).where(User.email == "admin@example.com")
        result = await db.execute(query)
        admin = result.scalar_one_or_none()
        
        if admin:
            # Yeni şifreyi argon2 ile hashle
            new_password_hash = ph.hash("admin123")
            
            # Güncelle
            admin.password_hash = new_password_hash
            await db.commit()
            print(f"✅ Admin şifresi güncellendi!")
            print(f"   Email: {admin.email}")
            print(f"   Yeni hash: {new_password_hash[:50]}...")
        else:
            print("❌ Admin kullanıcısı bulunamadı!")

if __name__ == "__main__":
    asyncio.run(reset_admin_password())
