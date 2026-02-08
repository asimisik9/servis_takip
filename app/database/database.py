from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from ..core.config import settings
import logging

logger = logging.getLogger(__name__)

# Asenkron veritabanı motorunu oluşturun
# Production için pool ayarları
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.ENVIRONMENT == "development",
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    pool_recycle=settings.POSTGRES_POOL_RECYCLE,
    pool_pre_ping=True
)

# Asenkron oturum oluşturucu
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Tüm tabloları oluşturmak için kullanılacak fonksiyon
async def create_tables():
    logger.info("Veritabanı tabloları oluşturuluyor...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Veritabanı tabloları başarıyla oluşturuldu.")
    
    