"""Tüm kullanıcıların şifresini argon2 ile günceller"""
import asyncio
from sqlalchemy import select
from app.database.models.user import User
from app.database.database import AsyncSessionLocal
from argon2 import PasswordHasher

ph = PasswordHasher()

async def reset_all_passwords():
    async with AsyncSessionLocal() as db:
        # Tüm kullanıcıları getir
        query = select(User)
        result = await db.execute(query)
        users = result.scalars().all()
        
        # Her kullanıcı için şifre belirle ve hashle
        password_map = {
            "admin@example.com": "admin123",
            "admin2@example.com": "admin123",
            "driver@example.com": "driver123",
            "parent@example.com": "parent123"
        }
        
        for user in users:
            if user.email in password_map:
                new_password = password_map[user.email]
                new_password_hash = ph.hash(new_password)
                user.password_hash = new_password_hash
                print(f"✅ {user.email} şifresi güncellendi (şifre: {new_password})")
            else:
                # Diğer kullanıcılar için varsayılan şifre
                new_password_hash = ph.hash("123456")
                user.password_hash = new_password_hash
                print(f"✅ {user.email} şifresi güncellendi (şifre: 123456)")
        
        await db.commit()
        print(f"\n🎉 Toplam {len(users)} kullanıcının şifresi güncellendi!")

if __name__ == "__main__":
    asyncio.run(reset_all_passwords())
