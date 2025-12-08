import asyncio
import sys
import os

# Add the current directory to sys.path to make 'app' module importable
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.database.database import AsyncSessionLocal
from app.database import models

async def check_data():
    async with AsyncSessionLocal() as db:
        # 1. Driverları bul (Role: sofor)
        print("Driverlar aranıyor...")
        try:
            # Enum değerini string olarak değil, Enum objesi olarak veya doğru string ile sorgulamalıyız.
            # SQLAlchemy Enum tipi genellikle string ile eşleşir ama case-sensitive'dir.
            result = await db.execute(select(models.User).where(models.User.role == 'sofor'))
            drivers = result.scalars().all()
            print(f"Toplam Driver (Şoför) Sayısı: {len(drivers)}")

            for driver in drivers:
                print(f"\nDriver: {driver.full_name} ({driver.email})")
                print(f"ID: {driver.id}")
                
                # 2. Otobüsünü bul
                result = await db.execute(select(models.Bus).where(models.Bus.current_driver_id == driver.id))
                bus = result.scalar_one_or_none()
                
                if bus:
                    print(f"  Atanmış Otobüs: {bus.plate_number}")
                    print(f"  Bus ID: {bus.id}")
                    
                    # 3. Öğrencileri bul
                    result = await db.execute(
                        select(models.Student)
                        .join(models.StudentBusAssignment)
                        .where(models.StudentBusAssignment.bus_id == bus.id)
                    )
                    students = result.scalars().all()
                    print(f"  Öğrenci Sayısı: {len(students)}")
                    for s in students:
                        print(f"    - {s.full_name}")
                else:
                    print("  Atanmış otobüs YOK.")
        except Exception as e:
            print(f"Hata oluştu: {e}")

if __name__ == "__main__":
    asyncio.run(check_data())
