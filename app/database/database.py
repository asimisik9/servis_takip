from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = "postgresql+asyncpg://isikasimm:mysecretpassword@localhost:5432/my-postgres-db"

# Asenkron veritabanı motorunu oluşturun
engine = create_async_engine(DATABASE_URL, echo=True)

# Asenkron oturum oluşturucu
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Tüm tabloları oluşturmak için kullanılacak fonksiyon
async def create_tables():
    print("Veritabanı tabloları oluşturuluyor...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Veritabanı tabloları başarıyla oluşturuldu.")
    
    